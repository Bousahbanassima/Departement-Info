import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pytest
from app import app, db, init_db, seed

@pytest.fixture
def client(tmp_path):
    app.config.update(TESTING=True, DATABASE=str(tmp_path/'test.db'), SECRET_KEY='test')
    with app.app_context(): init_db(); seed()
    return app.test_client()

def login(client, username):
    client.get('/login')
    with client.session_transaction() as sess: csrf=sess['csrf']
    return client.post('/login',data={'csrf':csrf,'username':username,'password':'demo1234'})

def post(client,path,data):
    with client.session_transaction() as sess: data['csrf']=sess['csrf']
    return client.post(path,data=data)

def test_dashboard_and_roles(client):
    assert login(client,'adjoint').status_code==302
    for path in ['/','/students','/teachers','/schedule','/absences','/teacher-absences','/justifications','/discipline','/notifications']:
        assert client.get(path).status_code==200, path
    assert client.get('/audit').status_code==403

def test_student_isolation_and_csrf(client):
    login(client,'etudiant')
    page=client.get('/students').get_data(as_text=True)
    assert 'Lina Boudiaf' in page and 'Adam Bensaid' not in page
    assert client.get('/discipline').status_code==403
    assert client.post('/justifications',data={'absence_id':'1'}).status_code==400
    assert post(client,'/absences',{'student_id':'2'}).status_code==403

def test_teacher_scope_and_duplicates(client):
    login(client,'enseignant')
    page=client.get('/students').get_data(as_text=True)
    assert 'Lina Boudiaf' in page and 'Sara Benameur' not in page
    assert post(client,'/absences',{'student_id':'5','session_id':'2','date':'2026-10-01'}).status_code==302
    with app.app_context(): assert db().execute("SELECT count(*) FROM absences WHERE student_id=5 AND date='2026-10-01'").fetchone()[0]==0
    payload={'student_id':'2','session_id':'1','date':'2026-10-01'}
    post(client,'/absences',payload.copy()); post(client,'/absences',payload.copy())
    with app.app_context(): assert db().execute("SELECT count(*) FROM absences WHERE student_id=2 AND date='2026-10-01'").fetchone()[0]==1

def test_justification_workflow(client):
    login(client,'adjoint')
    post(client,'/absences',{'student_id':'1','session_id':'1','date':'2026-10-01'})
    with app.app_context(): aid=db().execute("SELECT id FROM absences WHERE student_id=1 AND date='2026-10-01'").fetchone()[0]
    post(client,'/logout',{})
    login(client,'etudiant'); post(client,'/justifications',{'absence_id':str(aid),'reason':'Motif fictif'})
    with app.app_context():
        j=db().execute('SELECT id FROM justifications WHERE absence_id=?',(aid,)).fetchone()[0]
        assert db().execute('SELECT status FROM absences WHERE id=?',(aid,)).fetchone()[0]=='En attente'
    post(client,'/logout',{}); login(client,'scolarite')
    post(client,f'/justifications/{j}/decision',{'decision':'Accepté','note':'Vérifié'})
    with app.app_context():
        assert db().execute('SELECT status FROM absences WHERE id=?',(aid,)).fetchone()[0]=='Justifiée'
        assert db().execute('SELECT count(*) FROM notifications WHERE user_id=6').fetchone()[0]>=2

def test_commission_assignment(client):
    login(client,'commission')
    assert client.get('/discipline').status_code==200
    assert client.get('/students').status_code==403
    with app.app_context():
        db().execute("INSERT INTO users(username,name,role,password) SELECT 'other','Autre','commission',password FROM users LIMIT 1")
        other=db().execute("SELECT id FROM users WHERE username='other'").fetchone()[0]
        db().execute("UPDATE discipline SET assigned_to=? WHERE id=1",(other,)); db().commit()
    assert b'DISC-DEMO-001' not in client.get('/discipline').data
    assert post(client,'/discipline/1/status',{'status':'Clôturé','note':'Fictif'}).status_code==403

def test_teacher_creation_and_exam_dashboard(client):
    login(client,'scolarite')
    post(client,'/teachers',{'name':'Enseignant Fictif','grade':'MCA','specialty':'Informatique'})
    assert 'Enseignant Fictif' in client.get('/teachers').get_data(as_text=True)
    post(client,'/logout',{}); login(client,'examens')
    page=client.get('/')
    assert page.status_code==200 and 'Justificatifs en attente' not in page.get_data(as_text=True)
    assert client.get('/justifications').status_code==403

def test_student_absence_correction_and_restore(client):
    login(client,'enseignant')
    # Existing justification prevents cancelling the record behind a decision.
    post(client,'/absences/1/correction',{'action':'Annulée','reason':'Erreur'})
    with app.app_context(): assert db().execute('SELECT cancelled_at FROM absences WHERE id=1').fetchone()[0] is None
    # Teacher must own the session, and the reason is mandatory.
    assert post(client,'/absences/5/correction',{'action':'Annulée','reason':'Erreur'}).status_code==403
    post(client,'/absences/2/correction',{'action':'Annulée','reason':''})
    with app.app_context(): assert db().execute('SELECT cancelled_at FROM absences WHERE id=2').fetchone()[0] is None
    post(client,'/absences/2/correction',{'action':'Annulée','reason':'Présence confirmée'})
    with app.app_context():
        assert db().execute('SELECT cancelled_at FROM absences WHERE id=2').fetchone()[0] is not None
        assert db().execute('SELECT count(*) FROM absence_corrections WHERE absence_id=2').fetchone()[0]==1
    assert 'Absences annulées' in client.get('/absences').get_data(as_text=True)
    post(client,'/absences/2/correction',{'action':'Rétablie','reason':'Nouvelle vérification'})
    with app.app_context():
        assert db().execute('SELECT cancelled_at FROM absences WHERE id=2').fetchone()[0] is None
        assert [x[0] for x in db().execute('SELECT action FROM absence_corrections WHERE absence_id=2 ORDER BY id')]==['Annulée','Rétablie']

def test_teacher_absence_recovery_workflow(client):
    import datetime
    today=datetime.date.today()
    sunday=today-datetime.timedelta(days=(today.weekday()-6)%7+14)
    date=sunday.isoformat()
    login(client,'enseignant')
    assert post(client,'/teacher-absences',{'session_id':'2','date':date}).status_code==403
    post(client,'/teacher-absences',{'session_id':'1','date':date})
    post(client,'/teacher-absences',{'session_id':'1','date':date})
    with app.app_context():
        rows=db().execute('SELECT * FROM teacher_absences WHERE session_id=1 AND date=?',(date,)).fetchall()
        assert len(rows)==1
        aid=rows[0]['id']
    # The group and teacher already have a Sunday session at this time.
    post(client,'/recoveries',{'absence_id':str(aid),'date':date,'start_time':'08:45','end_time':'09:30','room':'Autre salle'})
    with app.app_context(): assert db().execute('SELECT count(*) FROM teacher_recoveries WHERE absence_id=?',(aid,)).fetchone()[0]==0
    post(client,'/recoveries',{'absence_id':str(aid),'date':date,'start_time':'15:00','end_time':'16:00','room':'Salle 08'})
    with app.app_context():
        r=db().execute('SELECT * FROM teacher_recoveries WHERE absence_id=?',(aid,)).fetchone(); assert r['status']=='Proposée'; rid=r['id']
    assert post(client,f'/recoveries/{rid}/status',{'status':'Programmée','reason':'Validation'}).status_code==403
    post(client,'/logout',{}); login(client,'adjoint')
    post(client,f'/recoveries/{rid}/status',{'status':'Programmée','reason':'Validé'})
    post(client,f'/recoveries/{rid}/status',{'status':'Effectuée','reason':'Séance assurée'})
    with app.app_context():
        assert db().execute('SELECT status FROM teacher_recoveries WHERE id=?',(rid,)).fetchone()[0]=='Effectuée'
        assert [r[0] for r in db().execute('SELECT status FROM teacher_recovery_events WHERE recovery_id=? ORDER BY id',(rid,))]==['Proposée','Programmée','Effectuée']
    assert client.get('/teacher-absences').status_code==200

def test_versioned_migration_preserves_old_data(tmp_path):
    import sqlite3
    path=tmp_path/'old.db'
    conn=sqlite3.connect(path)
    conn.executescript((Path(__file__).resolve().parents[1]/'schema.sql').read_text())
    conn.execute("INSERT INTO users(id,username,name,role,password) VALUES(1,'legacy','Ancien','admin','hash')")
    conn.commit(); conn.close()
    app.config.update(TESTING=True,DATABASE=str(path))
    with app.app_context():
        init_db(); init_db()
        assert db().execute("SELECT name FROM users WHERE id=1").fetchone()[0]=='Ancien'
        assert db().execute("SELECT count(*) FROM schema_migrations WHERE version='001_absence_workflows.sql'").fetchone()[0]==1
        assert 'cancelled_at' in [r['name'] for r in db().execute('PRAGMA table_info(absences)')]

def test_recovery_room_conflicts_and_permissions(client):
    import datetime
    today=datetime.date.today(); sunday=today-datetime.timedelta(days=(today.weekday()-6)%7+21)
    date=sunday.isoformat()
    login(client,'adjoint')
    for sid in ('1','2'): post(client,'/teacher-absences',{'session_id':sid,'date':date})
    with app.app_context():
        ids=[r[0] for r in db().execute('SELECT id FROM teacher_absences WHERE date=? ORDER BY session_id',(date,))]
    first={'absence_id':str(ids[0]),'date':date,'start_time':'15:00','end_time':'16:00','room':'Salle X'}
    post(client,'/recoveries',first)
    post(client,'/recoveries',{'absence_id':str(ids[1]),'date':date,'start_time':'15:30','end_time':'16:30','room':' salle x '})
    with app.app_context(): assert db().execute('SELECT count(*) FROM teacher_recoveries WHERE absence_id=?',(ids[1],)).fetchone()[0]==0
    post(client,'/recoveries',{'absence_id':str(ids[1]),'date':date,'start_time':'15:30','end_time':'16:30','room':'Salle Y'})
    with app.app_context(): assert db().execute('SELECT count(*) FROM teacher_recoveries WHERE absence_id=?',(ids[1],)).fetchone()[0]==1
    post(client,'/logout',{}); login(client,'enseignant')
    assert post(client,'/recoveries',{'absence_id':str(ids[1]),'date':date,'start_time':'17:00','end_time':'18:00','room':'Salle Z'}).status_code==403

def test_migration_rejects_duplicate_legacy_data_without_partial_change(tmp_path):
    import sqlite3
    path=tmp_path/'duplicates.db'; conn=sqlite3.connect(path)
    conn.executescript((Path(__file__).resolve().parents[1]/'schema.sql').read_text())
    conn.executescript("""INSERT INTO groups(id,name,level,specialty) VALUES(1,'G1','L2','Info');
    INSERT INTO teachers(id,name,grade,specialty) VALUES(1,'Fictif','MCA','Info');
    INSERT INTO sessions(id,day,start_time,end_time,module,kind,group_id,teacher_id,room) VALUES(1,'Lundi','08:30','10:00','Algo','Cours',1,1,'A');
    INSERT INTO teacher_absences(teacher_id,date,session_id,status) VALUES(1,'2026-01-05',1,'À récupérer');
    INSERT INTO teacher_absences(teacher_id,date,session_id,status) VALUES(1,'2026-01-05',1,'À récupérer');""")
    conn.close(); app.config.update(TESTING=True,DATABASE=str(path))
    with app.app_context():
        with pytest.raises(sqlite3.IntegrityError): init_db()
        db().rollback()
        assert db().execute('SELECT count(*) FROM teacher_absences').fetchone()[0]==2
        assert 'cancelled_at' not in [r['name'] for r in db().execute('PRAGMA table_info(absences)')]
        assert db().execute('SELECT count(*) FROM schema_migrations').fetchone()[0]==0
