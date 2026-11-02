import os, sqlite3, secrets, datetime, functools
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort, send_file, g
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

BASE = Path(__file__).resolve().parent
app = Flask(__name__, instance_relative_config=True)
app.config.update(SECRET_KEY=os.environ.get('SECRET_KEY', 'dev-only-change-me'), DATABASE=os.environ.get('DATABASE', str(BASE/'instance'/'infodept.db')), MAX_CONTENT_LENGTH=5*1024*1024, SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax', SESSION_COOKIE_SECURE=os.environ.get('HTTPS_ONLY') == '1')
Path(app.instance_path).mkdir(exist_ok=True)
UPLOADS = Path(app.instance_path)/'uploads'; UPLOADS.mkdir(exist_ok=True)

def db():
    if 'db' not in g:
        g.db = sqlite3.connect(app.config['DATABASE']); g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys=ON')
    return g.db
@app.teardown_appcontext
def close_db(e):
    if 'db' in g: g.db.close()
def q(sql, args=()): return db().execute(sql,args).fetchall()
def one(sql,args=()): return db().execute(sql,args).fetchone()
def audit(action, target=''):
    db().execute('INSERT INTO audit(user_id,action,target) VALUES(?,?,?)',(session.get('uid'),action,str(target)))
def notify(user_id, message):
    if user_id: db().execute('INSERT INTO notifications(user_id,message) VALUES(?,?)',(user_id,message))

def init_db():
    db().executescript((BASE/'schema.sql').read_text())
    db().execute('CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)')
    db().commit()
    for path in sorted((BASE/'migrations').glob('*.sql')):
        version = path.name
        if not one('SELECT version FROM schema_migrations WHERE version=?', (version,)):
            # Version names come only from the local migrations directory.
            escaped = version.replace("'", "''")
            db().executescript('BEGIN IMMEDIATE;\n' + path.read_text() + "\nINSERT INTO schema_migrations(version) VALUES ('" + escaped + "');\nCOMMIT;")

def seed():
    if one('SELECT id FROM users LIMIT 1'): return
    roles=['admin','chef','adjoint','scolarite','enseignant','etudiant','examens','commission']
    names=['Administrateur système','Amine Benali','Samira Mansouri','Nadia Khelifi','Yacine Amrani','Lina Boudiaf','Karim Saidi','Meriem Hamidi']
    for role,name in zip(roles,names):
        db().execute('INSERT INTO users(username,name,role,password) VALUES(?,?,?,?)',(role,name,role,generate_password_hash('demo1234')))
    db().executemany('INSERT INTO groups(name,level,specialty) VALUES(?,?,?)', [('Groupe 01','L2','Informatique'),('Groupe 02','L2','Informatique'),('Groupe 01','L3','Systèmes informatiques'),('Groupe 02','L3','Systèmes informatiques'),('Groupe 01','M1','Systèmes d’information'),('Groupe 01','M2','Réseaux et systèmes distribués')])
    students=[('2022301001','Lina','Boudiaf',1,6),('2022301002','Adam','Bensaid',1,None),('2022301003','Inès','Rahmani',1,None),('2022301004','Yanis','Belkacem',2,None),('2021301005','Sara','Benameur',3,None),('2021301006','Rayan','Messaoudi',4,None),('2020301007','Maya','Boualem',5,None),('2020301008','Nassim','Merabet',6,None)]
    db().executemany('INSERT INTO students(matricule,first_name,last_name,group_id,user_id) VALUES(?,?,?,?,?)',students)
    db().executemany('INSERT INTO teachers(name,grade,specialty,user_id) VALUES(?,?,?,?)',[('Yacine Amrani','Maître de conférences A','Intelligence artificielle',5),('Leïla Kaci','Maître de conférences B','Systèmes d’information',None),('Sofiane Touati','Maître assistant A','Réseaux',None),('Nour El Houda Salem','Maître de conférences A','Génie logiciel',None)])
    db().executemany('INSERT INTO sessions(day,start_time,end_time,module,kind,group_id,teacher_id,room) VALUES(?,?,?,?,?,?,?,?)', [('Dimanche','08:30','10:00','Algorithmique 2','Cours',1,1,'Amphi A'),('Dimanche','10:15','11:45','Bases de données','TD',3,2,'Salle 12'),('Lundi','08:30','10:00','Architecture des ordinateurs','Cours',2,3,'Amphi B'),('Lundi','10:15','11:45','Algorithmique 2','TD',1,1,'Salle 08'),('Mardi','09:00','10:30','Génie logiciel','Cours',5,4,'Salle 14'),('Mercredi','13:00','14:30','Réseaux informatiques','TP',6,3,'Labo 03')])
    today=datetime.date.today(); dates=[(today-datetime.timedelta(days=x)).isoformat() for x in (2,3,5,7,10,12)]
    db().executemany('INSERT INTO absences(student_id,session_id,date,status,declared_by) VALUES(?,?,?,?,?)',[(1,1,dates[0],'En attente',5),(2,1,dates[1],'Non justifiée',5),(3,1,dates[2],'Justifiée',5),(4,3,dates[3],'Non justifiée',2),(5,2,dates[4],'Non justifiée',2),(3,4,dates[5],'Justifiée',2)])
    db().execute("INSERT INTO justifications(absence_id,reason,status) VALUES(1,'Rendez-vous médical — données fictives','En attente')")
    sunday=(today-datetime.timedelta(days=(today.weekday()-6)%7)).isoformat()
    cur=db().execute("INSERT INTO teacher_absences(teacher_id,date,session_id,status,declared_by) VALUES(1,?,1,'Déclarée',5)",(sunday,))
    db().execute("INSERT INTO teacher_absence_events(absence_id,user_id,event,reason) VALUES(?,5,'Déclarée','Donnée fictive initiale')",(cur.lastrowid,))
    db().execute("INSERT INTO discipline(ref,student_id,incident_date,description,status,assigned_to,created_by) VALUES('DISC-DEMO-001',2,?,'Incident fictif à instruire.','En instruction',8,2)",(dates[4],))
    notify(4,'Un justificatif est en attente de traitement.')
    notify(6,'Votre justificatif est en attente de traitement.')
    db().commit()

@app.before_request
def security():
    if request.method == 'POST':
        if not session.get('csrf') or not secrets.compare_digest(session['csrf'], request.form.get('csrf','')): abort(400)
    g.user = one('SELECT id,username,name,role FROM users WHERE id=?',(session['uid'],)) if session.get('uid') else None
    if request.endpoint not in ('login','static') and not g.user: return redirect(url_for('login'))
@app.context_processor
def globals_():
    if 'csrf' not in session: session['csrf']=secrets.token_urlsafe(32)
    return {'csrf':session['csrf'],'user':g.get('user'),'unread':one('SELECT count(*) n FROM notifications WHERE user_id=? AND read_at IS NULL',(g.user['id'],))['n'] if g.get('user') else 0}
@app.after_request
def headers(r):
    r.headers['X-Content-Type-Options']='nosniff'; r.headers['Referrer-Policy']='same-origin'
    if os.environ.get('ALLOW_EMBED') != '1': r.headers['X-Frame-Options']='DENY'
    r.headers['Content-Security-Policy']="default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; form-action 'self'" + ("; frame-ancestors 'none'" if os.environ.get('ALLOW_EMBED') != '1' else '')
    return r

def allowed(*roles):
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*a,**kw):
            if not g.user or g.user['role'] not in roles: abort(403)
            return fn(*a,**kw)
        return wrapper
    return deco
STAFF=('admin','chef','adjoint','scolarite')
MANAGERS=('admin','chef','adjoint')
ACADEMIC=STAFF+('enseignant','examens')

def student_scope():
    if g.user['role']=='etudiant': return ' AND s.user_id=?',[g.user['id']]
    if g.user['role']=='enseignant': return ' AND EXISTS (SELECT 1 FROM sessions x JOIN teachers t ON t.id=x.teacher_id WHERE x.group_id=s.group_id AND t.user_id=?)',[g.user['id']]
    return '',[]
def absence_scope():
    if g.user['role']=='etudiant': return ' AND s.user_id=?',[g.user['id']]
    if g.user['role']=='enseignant': return ' AND t.user_id=?',[g.user['id']]
    return '',[]

@app.route('/login',methods=['GET','POST'])
def login():
    if request.method=='POST':
        username=request.form.get('username','').strip().lower(); u=one('SELECT * FROM users WHERE username=?',(username,))
        # Fixed generic response; production must add centralized rate limiting.
        if u and check_password_hash(u['password'],request.form.get('password','')):
            session.clear(); session['uid']=u['id']; session['csrf']=secrets.token_urlsafe(32); audit('Connexion'); db().commit(); return redirect(url_for('dashboard'))
        flash('Identifiant ou mot de passe incorrect.','error')
    return render_template('login.html')
@app.post('/logout')
def logout(): session.clear(); return redirect(url_for('login'))

@app.get('/')
def dashboard():
    role=g.user['role']; scope,args=absence_scope()
    absences=q('SELECT a.*,s.first_name,s.last_name,s.matricule, gr.name group_name,gr.level, se.module,se.kind FROM absences a JOIN students s ON s.id=a.student_id JOIN groups gr ON gr.id=s.group_id JOIN sessions se ON se.id=a.session_id JOIN teachers t ON t.id=se.teacher_id WHERE a.cancelled_at IS NULL'+scope+' ORDER BY a.date DESC,a.id DESC LIMIT 5',args) if role in ACADEMIC+('etudiant',) else []
    counts={}
    if role in STAFF+('examens',):
        counts={'students':one('SELECT count(*) n FROM students')['n'],'teachers':one('SELECT count(*) n FROM teachers')['n'],'groups':one('SELECT count(*) n FROM groups')['n']}
        if role in STAFF: counts['pending']=one("SELECT count(*) n FROM justifications WHERE status='En attente'")['n']
    elif role in ('enseignant','etudiant'):
        counts={'absences':one('SELECT count(*) n FROM absences a JOIN students s ON s.id=a.student_id JOIN sessions se ON se.id=a.session_id JOIN teachers t ON t.id=se.teacher_id WHERE a.cancelled_at IS NULL'+scope,args)['n'],'pending':one("SELECT count(*) n FROM absences a JOIN students s ON s.id=a.student_id JOIN sessions se ON se.id=a.session_id JOIN teachers t ON t.id=se.teacher_id WHERE a.cancelled_at IS NULL AND a.status='En attente'"+scope,args)['n']}
    stats=q("SELECT a.status,count(*) n FROM absences a JOIN students s ON s.id=a.student_id JOIN sessions se ON se.id=a.session_id JOIN teachers t ON t.id=se.teacher_id WHERE a.cancelled_at IS NULL"+scope+" GROUP BY a.status",args) if role in ACADEMIC+('etudiant',) else []
    teacher_open=None
    if role in STAFF+('enseignant',):
        teacher_open=one("SELECT count(*) n FROM teacher_absences a JOIN teachers t ON t.id=a.teacher_id WHERE NOT EXISTS (SELECT 1 FROM teacher_recoveries r WHERE r.absence_id=a.id AND r.status='Effectuée')"+(' AND t.user_id=?' if role=='enseignant' else ''), (g.user['id'],) if role=='enseignant' else ())['n']
    return render_template('dashboard.html',counts=counts,absences=absences,stats=stats,teacher_open=teacher_open, sessions=q('SELECT se.*,gr.level,gr.name group_name,t.name teacher FROM sessions se JOIN groups gr ON gr.id=se.group_id JOIN teachers t ON t.id=se.teacher_id'+ (' WHERE t.user_id=?' if role=='enseignant' else ' WHERE gr.id=(SELECT group_id FROM students WHERE user_id=?)' if role=='etudiant' else '' )+' ORDER BY se.id LIMIT 4', (g.user['id'],) if role in ('enseignant','etudiant') else ()) if role in ACADEMIC+('etudiant',) else [], role=role)

@app.route('/students',methods=['GET','POST'])
@allowed(*ACADEMIC,'etudiant')
def students():
    if request.method=='POST':
        if g.user['role'] not in STAFF: abort(403)
        vals=[request.form.get(x,'').strip() for x in ('matricule','first_name','last_name','group_id')]
        if not all(vals) or any(len(v)>100 for v in vals[:3]) or not one('SELECT id FROM groups WHERE id=?',(vals[3],)): flash('Tous les champs sont obligatoires.','error')
        else:
            try:
                cur=db().execute('INSERT INTO students(matricule,first_name,last_name,group_id) VALUES(?,?,?,?)',vals); audit('Création étudiant',cur.lastrowid); db().commit(); flash('Étudiant ajouté.','success')
            except sqlite3.IntegrityError: db().rollback(); flash('Ce matricule existe déjà.','error')
        return redirect(url_for('students'))
    term=request.args.get('q','').strip(); scope,args=student_scope(); rows=q('SELECT s.*,gr.name group_name,gr.level,gr.specialty FROM students s JOIN groups gr ON gr.id=s.group_id WHERE (s.first_name LIKE ? OR s.last_name LIKE ? OR s.matricule LIKE ? OR gr.level LIKE ? OR gr.specialty LIKE ?)'+scope+' ORDER BY s.last_name', ['%'+term+'%']*5+args)
    return render_template('students.html',rows=rows,groups=q('SELECT * FROM groups'),term=term,can_create=g.user['role'] in STAFF)

@app.route('/teachers',methods=['GET','POST'])
@allowed(*ACADEMIC)
def teachers():
    if request.method=='POST':
        if g.user['role'] not in STAFF: abort(403)
        values=[request.form.get(x,'').strip() for x in ('name','grade','specialty')]
        if not all(values) or any(len(v)>100 for v in values): flash('Tous les champs sont obligatoires (100 caractères maximum).','error')
        else:
            cur=db().execute('INSERT INTO teachers(name,grade,specialty) VALUES(?,?,?)',values); audit('Création enseignant',cur.lastrowid); db().commit(); flash('Enseignant ajouté.','success')
        return redirect(url_for('teachers'))
    rows=q('SELECT * FROM teachers'+(' WHERE user_id=?' if g.user['role']=='enseignant' else '')+' ORDER BY name',(g.user['id'],) if g.user['role']=='enseignant' else ())
    return render_template('teachers.html',rows=rows,can_create=g.user['role'] in STAFF)

@app.get('/schedule')
@allowed(*ACADEMIC,'etudiant')
def schedule():
    role=g.user['role']; where=''; args=[]
    if role=='enseignant': where=' WHERE t.user_id=?'; args=[g.user['id']]
    if role=='etudiant': where=' WHERE gr.id=(SELECT group_id FROM students WHERE user_id=?)'; args=[g.user['id']]
    rows=q('SELECT se.*,gr.level,gr.name group_name,t.name teacher FROM sessions se JOIN groups gr ON gr.id=se.group_id JOIN teachers t ON t.id=se.teacher_id'+where+' ORDER BY se.id',args)
    return render_template('schedule.html',rows=rows)

@app.route('/absences',methods=['GET','POST'])
@allowed(*ACADEMIC,'etudiant')
def absences():
    role=g.user['role']; scope,args=absence_scope()
    if request.method=='POST':
        if role not in STAFF+('enseignant',): abort(403)
        sid=request.form.get('student_id'); sess=request.form.get('session_id'); date=request.form.get('date','')
        try: datetime.date.fromisoformat(date)
        except ValueError: flash('Date invalide.','error'); return redirect(url_for('absences'))
        valid=one('SELECT se.id FROM sessions se JOIN students s ON s.group_id=se.group_id JOIN teachers t ON t.id=se.teacher_id WHERE se.id=? AND s.id=?'+(' AND t.user_id=?' if role=='enseignant' else ''),(sess,sid,g.user['id']) if role=='enseignant' else (sess,sid))
        if not valid: flash('Étudiant ou séance non autorisé ou groupe incompatible.','error')
        else:
            try:
                cur=db().execute("INSERT INTO absences(student_id,session_id,date,status,declared_by) VALUES(?,?,?,'Non justifiée',?)",(sid,sess,date,g.user['id'])); audit('Déclaration absence',cur.lastrowid); st=one('SELECT user_id FROM students WHERE id=?',(sid,)); notify(st['user_id'],'Une absence a été enregistrée dans votre dossier.'); db().commit(); flash('Absence enregistrée.','success')
            except sqlite3.IntegrityError: db().rollback(); flash('Cette absence existe déjà.','error')
        return redirect(url_for('absences'))
    status=request.args.get('status',''); filt=' AND a.status=?' if status in ('Non justifiée','Justifiée','En attente') else ''
    rows=q('SELECT a.*,s.first_name,s.last_name,s.matricule,gr.level,gr.name group_name,se.module,se.kind FROM absences a JOIN students s ON s.id=a.student_id JOIN groups gr ON gr.id=s.group_id JOIN sessions se ON se.id=a.session_id JOIN teachers t ON t.id=se.teacher_id WHERE a.cancelled_at IS NULL'+scope+filt+' ORDER BY a.date DESC,a.id DESC',args+([status] if filt else []))
    stscope,stargs=student_scope(); students_=q('SELECT s.*,gr.level,gr.name group_name FROM students s JOIN groups gr ON gr.id=s.group_id WHERE 1=1'+stscope+' ORDER BY s.last_name',stargs)
    sessions_=q('SELECT se.*,gr.level,gr.name group_name FROM sessions se JOIN groups gr ON gr.id=se.group_id JOIN teachers t ON t.id=se.teacher_id'+(' WHERE t.user_id=?' if role=='enseignant' else ''),(g.user['id'],) if role=='enseignant' else ())
    corrections=[]; cancelled=[]
    if role in STAFF+('enseignant',):
        cancelled=q('SELECT a.*,s.first_name,s.last_name,se.module FROM absences a JOIN students s ON s.id=a.student_id JOIN sessions se ON se.id=a.session_id JOIN teachers t ON t.id=se.teacher_id WHERE a.cancelled_at IS NOT NULL'+scope+' ORDER BY a.cancelled_at DESC',args)
        corrections=q('SELECT c.*, u.name actor, s.first_name,s.last_name,se.module,a.date,a.cancelled_at FROM absence_corrections c JOIN users u ON u.id=c.user_id JOIN absences a ON a.id=c.absence_id JOIN students s ON s.id=a.student_id JOIN sessions se ON se.id=a.session_id JOIN teachers t ON t.id=se.teacher_id WHERE 1=1'+scope+' ORDER BY c.id DESC LIMIT 100',args)
    return render_template('absences.html',rows=rows,students=students_,sessions=sessions_,can_create=role in STAFF+('enseignant',),status=status,corrections=corrections,cancelled=cancelled)


@app.post('/absences/<int:id>/correction')
@allowed(*STAFF,'enseignant')
def correct_absence(id):
    db().execute('BEGIN IMMEDIATE')
    row=one('SELECT a.*,s.user_id student_user,t.user_id teacher_user FROM absences a JOIN students s ON s.id=a.student_id JOIN sessions se ON se.id=a.session_id JOIN teachers t ON t.id=se.teacher_id WHERE a.id=?',(id,))
    if not row: abort(404)
    if g.user['role']=='enseignant' and row['teacher_user'] != g.user['id']: abort(403)
    reason=request.form.get('reason','').strip(); action=request.form.get('action')
    if not reason or len(reason)>500 or action not in ('Annulée','Rétablie'):
        flash('Un motif de correction valide est obligatoire.','error'); return redirect(url_for('absences'))
    if (action=='Annulée' and row['cancelled_at']) or (action=='Rétablie' and not row['cancelled_at']):
        flash('Cette correction ne correspond pas à l’état actuel.','error'); return redirect(url_for('absences'))
    if action=='Annulée' and one('SELECT id FROM justifications WHERE absence_id=?',(id,)):
        flash('Correction impossible : une demande de justificatif est liée à cette absence. Un traitement administratif est nécessaire.','error'); return redirect(url_for('absences'))
    db().execute("UPDATE absences SET cancelled_at=CASE WHEN ?='Annulée' THEN CURRENT_TIMESTAMP ELSE NULL END WHERE id=?",(action,id))
    db().execute('INSERT INTO absence_corrections(absence_id,user_id,action,reason) VALUES(?,?,?,?)',(id,g.user['id'],action,reason))
    audit('Correction absence',id); notify(row['student_user'],'Une correction a été enregistrée sur votre relevé d’absences.'); db().commit()
    flash('Correction enregistrée et historisée.','success'); return redirect(url_for('absences'))

@app.route('/justifications',methods=['GET','POST'])
@allowed(*STAFF,'etudiant')
def justifications():
    role=g.user['role']
    if request.method=='POST':
        if role!='etudiant': abort(403)
        db().execute('BEGIN IMMEDIATE')
        aid=request.form.get('absence_id'); reason=request.form.get('reason','').strip(); a=one("SELECT a.id FROM absences a JOIN students s ON s.id=a.student_id WHERE a.id=? AND s.user_id=? AND a.cancelled_at IS NULL AND a.status='Non justifiée'",(aid,g.user['id']))
        if not a or not reason: flash('Absence invalide ou motif manquant.','error'); return redirect(url_for('justifications'))
        file=request.files.get('file'); stored=None; original=None
        if file and file.filename:
            data=file.read(); valid=(data.startswith(b'%PDF-') or data.startswith(b'\x89PNG\r\n\x1a\n') or data.startswith(b'\xff\xd8\xff'))
            if not valid: flash('Seuls les fichiers PDF, PNG et JPEG sont acceptés.','error'); return redirect(url_for('justifications'))
            stored=secrets.token_hex(24); original=secure_filename(file.filename) or 'document'; (UPLOADS/stored).write_bytes(data)
        cur=db().execute("INSERT INTO justifications(absence_id,reason,status,file_key,file_name) VALUES(?,?,'En attente',?,?)",(aid,reason,stored,original)); db().execute("UPDATE absences SET status='En attente' WHERE id=?",(aid,)); audit('Dépôt justificatif',cur.lastrowid)
        for u in q("SELECT id FROM users WHERE role='scolarite'"): notify(u['id'],'Un justificatif est en attente de traitement.')
        db().commit(); flash('Justificatif transmis.','success'); return redirect(url_for('justifications'))
    where=' WHERE s.user_id=?' if role=='etudiant' else ''; args=(g.user['id'],) if role=='etudiant' else ()
    rows=q('SELECT j.*,a.date,s.first_name,s.last_name,se.module FROM justifications j JOIN absences a ON a.id=j.absence_id JOIN students s ON s.id=a.student_id JOIN sessions se ON se.id=a.session_id'+where+' ORDER BY j.id DESC',args)
    available=q("SELECT a.id,a.date,se.module FROM absences a JOIN students s ON s.id=a.student_id JOIN sessions se ON se.id=a.session_id WHERE s.user_id=? AND a.cancelled_at IS NULL AND a.status='Non justifiée'",(g.user['id'],)) if role=='etudiant' else []
    return render_template('justifications.html',rows=rows,available=available)

@app.post('/justifications/<int:id>/decision')
@allowed(*STAFF)
def decision(id):
    db().execute('BEGIN IMMEDIATE')
    j=one('SELECT j.*,s.user_id FROM justifications j JOIN absences a ON a.id=j.absence_id JOIN students s ON s.id=a.student_id WHERE j.id=?',(id,)); result=request.form.get('decision'); note=request.form.get('note','').strip()
    if not j: abort(404)
    if j['status']!='En attente' or result not in ('Accepté','Refusé') or not note: flash('Décision invalide ou motif manquant.','error'); return redirect(url_for('justifications'))
    db().execute('UPDATE justifications SET status=?,decision_note=?,decided_by=?,decided_at=CURRENT_TIMESTAMP WHERE id=?',(result,note,g.user['id'],id)); db().execute('UPDATE absences SET status=? WHERE id=?',('Justifiée' if result=='Accepté' else 'Non justifiée',j['absence_id'])); audit('Décision justificatif',id); notify(j['user_id'],'Votre justificatif a été traité.'); db().commit(); flash('Décision enregistrée.','success'); return redirect(url_for('justifications'))
@app.get('/justifications/<int:id>/file')
@allowed(*STAFF,'etudiant')
def justification_file(id):
    row=one('SELECT j.*,s.user_id FROM justifications j JOIN absences a ON a.id=j.absence_id JOIN students s ON s.id=a.student_id WHERE j.id=?',(id,))
    if not row or not row['file_key']: abort(404)
    if g.user['role']=='etudiant' and row['user_id']!=g.user['id']: abort(403)
    audit('Téléchargement justificatif',id); db().commit(); return send_file(UPLOADS/row['file_key'],as_attachment=True,download_name=row['file_name'],mimetype='application/octet-stream')

@app.route('/discipline',methods=['GET','POST'])
@allowed(*MANAGERS,'commission')
def discipline():
    if request.method=='POST':
        if g.user['role'] not in MANAGERS: abort(403)
        student=request.form.get('student_id'); date=request.form.get('date',''); description=request.form.get('description','').strip(); assigned=request.form.get('assigned_to')
        try: datetime.date.fromisoformat(date)
        except ValueError: flash('Date invalide.','error'); return redirect(url_for('discipline'))
        if not description or not one('SELECT id FROM students WHERE id=?',(student,)) or not one("SELECT id FROM users WHERE id=? AND role='commission'",(assigned,)): flash('Données incomplètes.','error'); return redirect(url_for('discipline'))
        ref='DISC-'+secrets.token_hex(5).upper(); cur=db().execute("INSERT INTO discipline(ref,student_id,incident_date,description,status,assigned_to,created_by) VALUES(?,?,?,?,'En instruction',?,?)",(ref,student,date,description,assigned,g.user['id'])); audit('Création dossier disciplinaire',cur.lastrowid); notify(assigned,'Un dossier confidentiel vous a été attribué.'); db().commit(); flash('Dossier créé.','success'); return redirect(url_for('discipline'))
    where=' WHERE d.assigned_to=?' if g.user['role']=='commission' else ''; args=(g.user['id'],) if where else ()
    rows=q('SELECT d.*,s.first_name,s.last_name FROM discipline d JOIN students s ON s.id=d.student_id'+where+' ORDER BY d.id DESC',args); audit('Consultation dossiers disciplinaires'); db().commit()
    return render_template('discipline.html',rows=rows,students=q('SELECT * FROM students ORDER BY last_name') if g.user['role'] in MANAGERS else [],members=q("SELECT id,name FROM users WHERE role='commission'") if g.user['role'] in MANAGERS else [])
@app.post('/discipline/<int:id>/status')
@allowed(*MANAGERS,'commission')
def discipline_status(id):
    row=one('SELECT * FROM discipline WHERE id=?',(id,))
    if not row: abort(404)
    if g.user['role']=='commission' and row['assigned_to']!=g.user['id']: abort(403)
    status=request.form.get('status'); note=request.form.get('note','').strip()
    if status not in ('En instruction','En attente','Clôturé') or not note: flash('Statut ou motif invalide.','error'); return redirect(url_for('discipline'))
    db().execute('UPDATE discipline SET status=? WHERE id=?',(status,id)); db().execute('INSERT INTO discipline_history(discipline_id,user_id,status,note) VALUES(?,?,?,?)',(id,g.user['id'],status,note)); audit('Modification dossier disciplinaire',id); db().commit(); flash('Suivi enregistré. Aucune décision disciplinaire automatique.','success'); return redirect(url_for('discipline'))

@app.route('/notifications',methods=['GET','POST'])
def notifications():
    if request.method=='POST': db().execute('UPDATE notifications SET read_at=CURRENT_TIMESTAMP WHERE user_id=? AND read_at IS NULL',(g.user['id'],)); db().commit(); return redirect(url_for('notifications'))
    return render_template('notifications.html',rows=q('SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC',(g.user['id'],)))

WEEKDAYS=('Lundi','Mardi','Mercredi','Jeudi','Vendredi','Samedi','Dimanche')

def iso_date(value):
    try:
        parsed=datetime.date.fromisoformat(value)
        return parsed if parsed.isoformat()==value else None
    except (ValueError, TypeError): return None

def iso_time(value):
    try:
        parsed=datetime.datetime.strptime(value,'%H:%M')
        return value if parsed.strftime('%H:%M')==value else None
    except (ValueError, TypeError): return None

def teacher_absence_access(id):
    row=one('SELECT a.*, t.user_id teacher_user,se.group_id,se.module,se.day,se.kind,t.name teacher FROM teacher_absences a JOIN teachers t ON t.id=a.teacher_id JOIN sessions se ON se.id=a.session_id WHERE a.id=?',(id,))
    if not row: abort(404)
    if g.user['role']=='enseignant' and row['teacher_user']!=g.user['id']: abort(403)
    return row

def recovery_conflict(absence, date, start, end, room, ignore_id=None):
    day=WEEKDAYS[date.weekday()]
    # Recurring weekly schedules are treated as occupied for every matching weekday.
    scheduled=one("SELECT se.id FROM sessions se WHERE se.day=? AND se.start_time<? AND se.end_time>? AND (se.teacher_id=? OR se.group_id=? OR lower(trim(se.room))=lower(trim(?))) LIMIT 1",(day,end,start,absence['teacher_id'],absence['group_id'],room))
    if scheduled: return True
    return bool(one("""SELECT r.id FROM teacher_recoveries r
        JOIN teacher_absences a ON a.id=r.absence_id
        JOIN sessions se ON se.id=a.session_id
        WHERE r.date=? AND r.start_time<? AND r.end_time>?
        AND r.status IN ('Proposée','Programmée','Effectuée') AND (? IS NULL OR r.id<>?)
        AND (a.teacher_id=? OR se.group_id=? OR lower(trim(r.room))=lower(trim(?))) LIMIT 1""",
        (date.isoformat(),end,start,ignore_id,ignore_id,absence['teacher_id'],absence['group_id'],room)))

@app.route('/teacher-absences',methods=['GET','POST'])
@allowed(*STAFF,'enseignant')
def teacher_absences():
    role=g.user['role']
    if request.method=='POST':
        sess=request.form.get('session_id'); date_text=request.form.get('date',''); date=iso_date(date_text)
        session_row=one('SELECT se.*,t.user_id teacher_user FROM sessions se JOIN teachers t ON t.id=se.teacher_id WHERE se.id=?',(sess,))
        if not session_row or (role=='enseignant' and session_row['teacher_user']!=g.user['id']): abort(403)
        if not date or WEEKDAYS[date.weekday()]!=session_row['day']:
            flash('La date doit correspondre au jour habituel de la séance.','error'); return redirect(url_for('teacher_absences'))
        status='Déclarée' if role=='enseignant' else 'Constatée'
        try:
            db().execute('BEGIN IMMEDIATE')
            cur=db().execute('INSERT INTO teacher_absences(teacher_id,date,session_id,status,declared_by) VALUES(?,?,?,?,?)',(session_row['teacher_id'],date_text,sess,status,g.user['id']))
            db().execute('INSERT INTO teacher_absence_events(absence_id,user_id,event,reason) VALUES(?,?,?,?)',(cur.lastrowid,g.user['id'],status,'Déclaration initiale'))
            audit('Déclaration absence enseignant',cur.lastrowid)
            if role=='enseignant':
                for u in q("SELECT id FROM users WHERE role IN ('chef','adjoint')"): notify(u['id'],'Une séance non assurée a été déclarée.')
            else: notify(session_row['teacher_user'],'Une séance non assurée a été enregistrée dans votre espace.')
            db().commit(); flash('Séance non assurée enregistrée.','success')
        except sqlite3.IntegrityError:
            db().rollback(); flash('Cette séance non assurée existe déjà pour cette date.','error')
        return redirect(url_for('teacher_absences'))
    args=(g.user['id'],) if role=='enseignant' else ()
    where=' WHERE t.user_id=?' if role=='enseignant' else ''
    rows=q('SELECT a.*,t.name,se.module,se.kind,gr.level,gr.name group_name FROM teacher_absences a JOIN teachers t ON t.id=a.teacher_id JOIN sessions se ON se.id=a.session_id JOIN groups gr ON gr.id=se.group_id'+where+' ORDER BY a.date DESC',args)
    sessions_=q('SELECT se.*,t.name teacher,gr.level,gr.name group_name FROM sessions se JOIN teachers t ON t.id=se.teacher_id JOIN groups gr ON gr.id=se.group_id'+where+' ORDER BY se.id',args)
    recoveries=q('SELECT r.*,a.date absence_date,t.name teacher,se.module,gr.level,gr.name group_name FROM teacher_recoveries r JOIN teacher_absences a ON a.id=r.absence_id JOIN teachers t ON t.id=a.teacher_id JOIN sessions se ON se.id=a.session_id JOIN groups gr ON gr.id=se.group_id'+where+' ORDER BY r.id DESC',args)
    events=q('SELECT e.*,u.name actor,t.name teacher,se.module,a.date FROM teacher_absence_events e JOIN users u ON u.id=e.user_id JOIN teacher_absences a ON a.id=e.absence_id JOIN teachers t ON t.id=a.teacher_id JOIN sessions se ON se.id=a.session_id'+where+' ORDER BY e.id DESC LIMIT 100',args)
    recovery_events=q('SELECT e.*,u.name actor,se.module,r.date,t.name teacher FROM teacher_recovery_events e JOIN users u ON u.id=e.user_id JOIN teacher_recoveries r ON r.id=e.recovery_id JOIN teacher_absences a ON a.id=r.absence_id JOIN teachers t ON t.id=a.teacher_id JOIN sessions se ON se.id=a.session_id'+where+' ORDER BY e.id DESC LIMIT 100',args)
    return render_template('teacher_absences.html',rows=rows,sessions=sessions_,recoveries=recoveries,events=events,recovery_events=recovery_events,staff=role in STAFF)

@app.post('/teacher-absences/<int:id>/status')
@allowed(*STAFF)
def teacher_absence_status(id):
    db().execute('BEGIN IMMEDIATE'); absence=teacher_absence_access(id)
    status=request.form.get('status'); reason=request.form.get('reason','').strip()
    if status not in ('Déclarée','Constatée','En vérification','Justifiée') or not reason or len(reason)>500 or status==absence['status']:
        flash('Statut différent et motif non confidentiel obligatoires.','error'); return redirect(url_for('teacher_absences'))
    db().execute('UPDATE teacher_absences SET status=? WHERE id=?',(status,id))
    db().execute('INSERT INTO teacher_absence_events(absence_id,user_id,event,reason) VALUES(?,?,?,?)',(id,g.user['id'],status,reason))
    audit('Suivi absence enseignant',id); notify(absence['teacher_user'],'Le suivi d’une séance non assurée a été mis à jour.'); db().commit()
    flash('Suivi enregistré.','success'); return redirect(url_for('teacher_absences'))

@app.post('/recoveries')
@allowed(*STAFF,'enseignant')
def propose_recovery():
    id=request.form.get('absence_id',type=int)
    if id is None: abort(400)
    db().execute('BEGIN IMMEDIATE'); absence=teacher_absence_access(id)
    date=iso_date(request.form.get('date','')); start=iso_time(request.form.get('start_time','')); end=iso_time(request.form.get('end_time','')); room=request.form.get('room','').strip()
    if not date or not start or not end or start>=end or not room or len(room)>100 or date.isoformat()<absence['date']:
        flash('Date, horaires ou salle invalides. La récupération ne peut précéder l’absence.','error'); return redirect(url_for('teacher_absences'))
    if one("SELECT id FROM teacher_recoveries WHERE absence_id=? AND status IN ('Proposée','Programmée','Effectuée')",(id,)):
        flash('Une récupération active existe déjà pour cette absence.','error'); return redirect(url_for('teacher_absences'))
    if recovery_conflict(absence,date,start,end,room):
        flash('Conflit avec une séance ou récupération du groupe, de l’enseignant ou de la salle.','error'); return redirect(url_for('teacher_absences'))
    cur=db().execute("INSERT INTO teacher_recoveries(absence_id,date,start_time,end_time,room,status,created_by) VALUES(?,?,?,?,?,'Proposée',?)",(id,date.isoformat(),start,end,room,g.user['id']))
    db().execute("INSERT INTO teacher_recovery_events(recovery_id,user_id,status,reason) VALUES(?,?,'Proposée','Proposition initiale')",(cur.lastrowid,g.user['id']))
    audit('Proposition récupération',cur.lastrowid)
    if g.user['role']=='enseignant':
        for u in q("SELECT id FROM users WHERE role IN ('chef','adjoint')"): notify(u['id'],'Une récupération est proposée et attend validation.')
    else: notify(absence['teacher_user'],'Une récupération a été proposée pour votre séance.')
    db().commit(); flash('Récupération proposée ; une validation administrative est nécessaire.','success'); return redirect(url_for('teacher_absences'))

@app.post('/recoveries/<int:id>/status')
@allowed(*STAFF,'enseignant')
def recovery_status(id):
    db().execute('BEGIN IMMEDIATE')
    recovery=one('SELECT * FROM teacher_recoveries WHERE id=?',(id,))
    if not recovery: abort(404)
    absence=teacher_absence_access(recovery['absence_id'])
    status=request.form.get('status'); reason=request.form.get('reason','').strip()
    valid=(recovery['status']=='Proposée' and status in ('Programmée','Annulée')) or (recovery['status']=='Programmée' and status in ('Effectuée','Annulée'))
    if g.user['role']=='enseignant' and not (recovery['status']=='Proposée' and status=='Annulée'): abort(403)
    if not valid or not reason or len(reason)>500:
        flash('Transition invalide ou motif manquant.','error'); return redirect(url_for('teacher_absences'))
    if status=='Effectuée' and recovery['date']>datetime.date.today().isoformat():
        flash('Une récupération future ne peut être marquée effectuée.','error'); return redirect(url_for('teacher_absences'))
    if status=='Programmée' and recovery_conflict(absence,iso_date(recovery['date']),recovery['start_time'],recovery['end_time'],recovery['room'],id):
        flash('La récupération crée maintenant un conflit.','error'); return redirect(url_for('teacher_absences'))
    db().execute('UPDATE teacher_recoveries SET status=? WHERE id=?',(status,id))
    db().execute('INSERT INTO teacher_recovery_events(recovery_id,user_id,status,reason) VALUES(?,?,?,?)',(id,g.user['id'],status,reason))
    audit('Suivi récupération',id); notify(absence['teacher_user'],'Le suivi d’une récupération a été mis à jour.'); db().commit()
    flash('Suivi de récupération enregistré.','success'); return redirect(url_for('teacher_absences'))

@app.get('/audit')
@allowed('admin')
def audit_log(): return render_template('audit.html',rows=q('SELECT a.*,u.name FROM audit a LEFT JOIN users u ON u.id=a.user_id ORDER BY a.id DESC LIMIT 200'))

if __name__=='__main__':
    with app.app_context(): init_db(); seed()
    app.run(host='0.0.0.0',port=int(os.environ.get('PORT',5000)),debug=False)
