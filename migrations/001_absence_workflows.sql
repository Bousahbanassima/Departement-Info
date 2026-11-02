-- Les colonnes d'origine restent intactes ; les lignes déjà présentes sont conservées.
ALTER TABLE absences ADD COLUMN cancelled_at TEXT;
ALTER TABLE teacher_absences ADD COLUMN declared_by INTEGER REFERENCES users(id);
CREATE TABLE absence_corrections (
    id INTEGER PRIMARY KEY,
    absence_id INTEGER NOT NULL REFERENCES absences(id) ON DELETE RESTRICT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    action TEXT NOT NULL CHECK(action IN ('Annulée','Rétablie')),
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX teacher_absence_session_date ON teacher_absences(session_id,date);
CREATE TABLE teacher_absence_events (
    id INTEGER PRIMARY KEY,
    absence_id INTEGER NOT NULL REFERENCES teacher_absences(id) ON DELETE RESTRICT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    event TEXT NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE teacher_recoveries (
    id INTEGER PRIMARY KEY,
    absence_id INTEGER NOT NULL REFERENCES teacher_absences(id) ON DELETE RESTRICT,
    date TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    room TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('Proposée','Programmée','Effectuée','Annulée')),
    created_by INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK(start_time < end_time)
);
CREATE UNIQUE INDEX teacher_recovery_active ON teacher_recoveries(absence_id) WHERE status IN ('Proposée','Programmée','Effectuée');
CREATE TABLE teacher_recovery_events (
    id INTEGER PRIMARY KEY,
    recovery_id INTEGER NOT NULL REFERENCES teacher_recoveries(id) ON DELETE RESTRICT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    status TEXT NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
