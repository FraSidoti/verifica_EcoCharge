from flask import Flask, request, jsonify, session, render_template
from flask_cors import CORS
import mysql.connector
from mysql.connector import Error
import bcrypt
import logging
from datetime import datetime, timedelta

# Configurazione logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'charging-station-secret-key-2024'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
CORS(app, supports_credentials=True)

# Configurazione database
db_config = {
    'host': 'mysql-2421b5ed-iisgalvanimi-a660.j.aivencloud.com',
    'user': 'avnadmin',
    'password': 'AVNS_LMO-6TXmScL79ECZTot',
    'database': 'electric_vehicle_charging',
    'port': 23707
}

def get_db_connection():
    try:
        connection = mysql.connector.connect(**db_config)
        return connection
    except Error as e:
        logger.error(f"Error connecting to MySQL: {e}")
        return None

# Decorator per l'autenticazione
def login_required(f):
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

# Decorator per admin only
def admin_required(f):
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('user_type') != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

@app.before_request
def make_session_permanent():
    session.permanent = True

# ========== ROUTES DI AUTENTICAZIONE ==========

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    
    if not email or not password:
        return jsonify({'error': 'Email and password required'}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Prima controlla negli amministratori
        cursor.execute("SELECT * FROM amministratori WHERE email = %s", (email,))
        admin = cursor.fetchone()
        
        if admin:
            if bcrypt.checkpw(password.encode('utf-8'), admin['password_hash'].encode('utf-8')):
                session['user_id'] = admin['id_admin']
                session['user_type'] = 'admin'
                session['email'] = admin['email']
                session['name'] = f"{admin['nome']} {admin['cognome']}"
                logger.info(f"Admin login successful: {email}")
                return jsonify({
                    'message': 'Login successful',
                    'user_type': 'admin',
                    'user': {
                        'id': admin['id_admin'],
                        'email': admin['email'],
                        'name': f"{admin['nome']} {admin['cognome']}"
                    }
                })
        
        # Poi controlla negli utenti
        cursor.execute("SELECT * FROM utenti WHERE email = %s", (email,))
        user = cursor.fetchone()
        
        if user:
            if bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
                session['user_id'] = user['id_utente']
                session['user_type'] = 'user'
                session['email'] = user['email']
                session['name'] = f"{user['nome']} {user['cognome']}"
                logger.info(f"User login successful: {email}")
                return jsonify({
                    'message': 'Login successful',
                    'user_type': 'user',
                    'user': {
                        'id': user['id_utente'],
                        'email': user['email'],
                        'name': f"{user['nome']} {user['cognome']}"
                    }
                })
        
        logger.warning(f"Failed login attempt: {email}")
        return jsonify({'error': 'Invalid credentials'}), 401
        
    except Error as e:
        logger.error(f"Login error: {e}")
        return jsonify({'error': 'Database error'}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        conn.close()

@app.route('/api/logout', methods=['POST'])
def logout():
    user_email = session.get('email')
    session.clear()
    logger.info(f"User logged out: {user_email}")
    return jsonify({'message': 'Logout successful'})

@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    nome = data.get('nome')
    cognome = data.get('cognome')
    telefono = data.get('telefono')
    indirizzo = data.get('indirizzo')
    citta = data.get('citta')
    
    if not all([email, password, nome, cognome]):
        return jsonify({'error': 'Email, password, nome e cognome sono obbligatori'}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = conn.cursor()
        
        # Verifica se l'email esiste già
        cursor.execute("SELECT id_utente FROM utenti WHERE email = %s", (email,))
        if cursor.fetchone():
            return jsonify({'error': 'Email già registrata'}), 400
        
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        cursor.execute("""
            INSERT INTO utenti (email, password_hash, nome, cognome, telefono, indirizzo, citta)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (email, password_hash, nome, cognome, telefono, indirizzo, citta))
        
        conn.commit()
        logger.info(f"New user registered: {email}")
        return jsonify({'message': 'Registration successful'})
        
    except Error as e:
        conn.rollback()
        logger.error(f"Registration error: {e}")
        return jsonify({'error': 'Database error: ' + str(e)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        conn.close()

@app.route('/api/check-auth', methods=['GET'])
def check_auth():
    if 'user_id' in session:
        return jsonify({
            'authenticated': True,
            'user_type': session.get('user_type'),
            'user': {
                'id': session['user_id'],
                'email': session.get('email'),
                'name': session.get('name')
            }
        })
    return jsonify({'authenticated': False})

# ========== ROUTES PER LE COLONNINE ==========

@app.route('/api/colonnine', methods=['GET'])
def get_colonnine():
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT c.*, 
                   COUNT(r.id_ricarica) as utilizzi_totali,
                   AVG(r.energia_kwh) as energia_media,
                   SUM(r.energia_kwh) as energia_totale
            FROM colonnine c
            LEFT JOIN ricariche r ON c.id_colonnina = r.id_colonnina
            GROUP BY c.id_colonnina
            ORDER BY c.created_at DESC
        """)
        colonnine = cursor.fetchall()
        
        # Classifica l'utilizzo
        for colonnina in colonnine:
            utilizzi = colonnina['utilizzi_totali'] or 0
            if utilizzi == 0:
                colonnina['classificazione'] = 'nessuno'
            elif utilizzi < 5:
                colonnina['classificazione'] = 'basso'
            elif utilizzi < 15:
                colonnina['classificazione'] = 'medio'
            else:
                colonnina['classificazione'] = 'alto'
                
        return jsonify(colonnine)
        
    except Error as e:
        logger.error(f"Error getting colonnine: {e}")
        return jsonify({'error': 'Database error'}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        conn.close()

@app.route('/api/colonnine', methods=['POST'])
@admin_required
def add_colonnina():
    data = request.get_json()
    indirizzo = data.get('indirizzo')
    latitudine = data.get('latitudine')
    longitudine = data.get('longitudine')
    potenza_kw = data.get('potenza_kw')
    nil = data.get('nil')
    
    if not all([indirizzo, latitudine, longitudine, potenza_kw]):
        return jsonify({'error': 'Tutti i campi sono obbligatori'}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO colonnine (indirizzo, latitudine, longitudine, potenza_kw, nil)
            VALUES (%s, %s, %s, %s, %s)
        """, (indirizzo, latitudine, longitudine, potenza_kw, nil))
        
        conn.commit()
        logger.info(f"New colonnina added: {indirizzo}")
        return jsonify({'message': 'Colonnina added successfully'})
        
    except Error as e:
        conn.rollback()
        logger.error(f"Error adding colonnina: {e}")
        return jsonify({'error': 'Database error: ' + str(e)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        conn.close()

# ========== ROUTES PER LE PRENOTAZIONI ==========

@app.route('/api/prenotazioni', methods=['POST'])
@login_required
def create_prenotazione():
    if session.get('user_type') != 'user':
        return jsonify({'error': 'Only users can make reservations'}), 403
    
    data = request.get_json()
    id_veicolo = data.get('id_veicolo')
    id_colonnina = data.get('id_colonnina')
    data_ora_inizio = data.get('data_ora_inizio')
    data_ora_fine = data.get('data_ora_fine')
    energia_kwh = data.get('energia_kwh')
    
    if not all([id_veicolo, id_colonnina, data_ora_inizio, data_ora_fine]):
        return jsonify({'error': 'Tutti i campi sono obbligatori'}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = conn.cursor()
        
        # Verifica che il veicolo appartenga all'utente
        cursor.execute("SELECT id_utente FROM veicoli WHERE id_veicolo = %s", (id_veicolo,))
        veicolo = cursor.fetchone()
        
        if not veicolo or veicolo[0] != session['user_id']:
            return jsonify({'error': 'Veicolo non valido'}), 400
        
        # Verifica che la colonnina sia disponibile
        cursor.execute("""
            SELECT * FROM ricariche 
            WHERE id_colonnina = %s 
            AND ((data_ora_inizio BETWEEN %s AND %s) OR (data_ora_fine BETWEEN %s AND %s))
        """, (id_colonnina, data_ora_inizio, data_ora_fine, data_ora_inizio, data_ora_fine))
        
        if cursor.fetchone():
            return jsonify({'error': 'Colonnina non disponibile in questo orario'}), 400
        
        cursor.execute("""
            INSERT INTO ricariche (id_utente, id_veicolo, id_colonnina, data_ora_inizio, data_ora_fine, energia_kwh)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (session['user_id'], id_veicolo, id_colonnina, data_ora_inizio, data_ora_fine, energia_kwh))
        
        conn.commit()
        logger.info(f"New reservation created by user {session['user_id']}")
        return jsonify({'message': 'Prenotazione creata con successo'})
        
    except Error as e:
        conn.rollback()
        logger.error(f"Error creating reservation: {e}")
        return jsonify({'error': 'Database error: ' + str(e)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        conn.close()

@app.route('/api/veicoli', methods=['GET'])
@login_required
def get_veicoli():
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM veicoli WHERE id_utente = %s", (session['user_id'],))
        veicoli = cursor.fetchall()
        return jsonify(veicoli)
        
    except Error as e:
        logger.error(f"Error getting vehicles: {e}")
        return jsonify({'error': 'Database error'}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        conn.close()

# ========== ROUTES PER GLI AMMINISTRATORI ==========

@app.route('/api/admin/utenti', methods=['POST'])
@admin_required
def add_utente():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    nome = data.get('nome')
    cognome = data.get('cognome')
    telefono = data.get('telefono')
    indirizzo = data.get('indirizzo')
    citta = data.get('citta')
    
    if not all([email, password, nome, cognome]):
        return jsonify({'error': 'Email, password, nome e cognome sono obbligatori'}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = conn.cursor()
        
        # Verifica se l'email esiste già
        cursor.execute("SELECT id_utente FROM utenti WHERE email = %s", (email,))
        if cursor.fetchone():
            return jsonify({'error': 'Email già registrata'}), 400
        
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        cursor.execute("""
            INSERT INTO utenti (email, password_hash, nome, cognome, telefono, indirizzo, citta)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (email, password_hash, nome, cognome, telefono, indirizzo, citta))
        
        conn.commit()
        logger.info(f"New user added by admin: {email}")
        return jsonify({'message': 'Utente aggiunto con successo'})
        
    except Error as e:
        conn.rollback()
        logger.error(f"Error adding user: {e}")
        return jsonify({'error': 'Database error: ' + str(e)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        conn.close()

@app.route('/api/admin/statistiche', methods=['GET'])
@admin_required
def get_statistiche():
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Statistiche utilizzo colonnine
        cursor.execute("""
            SELECT c.id_colonnina, c.indirizzo, 
                   COUNT(r.id_ricarica) as utilizzi,
                   AVG(r.energia_kwh) as energia_media,
                   SUM(r.energia_kwh) as energia_totale
            FROM colonnine c
            LEFT JOIN ricariche r ON c.id_colonnina = r.id_colonnina
            GROUP BY c.id_colonnina
            ORDER BY utilizzi DESC
        """)
        stats_colonnine = cursor.fetchall()
        
        # Previsione domanda futura
        cursor.execute("""
            SELECT MONTH(data_ora_inizio) as mese, 
                   COUNT(*) as prenotazioni,
                   AVG(energia_kwh) as energia_media
            FROM ricariche
            WHERE data_ora_inizio >= DATE_SUB(NOW(), INTERVAL 12 MONTH)
            GROUP BY MONTH(data_ora_inizio)
            ORDER BY mese
        """)
        previsioni = cursor.fetchall()
        
        return jsonify({
            'stats_colonnine': stats_colonnine,
            'previsioni': previsioni
        })
        
    except Error as e:
        logger.error(f"Error getting statistics: {e}")
        return jsonify({'error': 'Database error'}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        conn.close()

# ========== ROUTES PER LA GESTIONE DEI VEICOLI ==========

@app.route('/api/veicoli', methods=['POST'])
@login_required
def add_veicolo():
    if session.get('user_type') != 'user':
        return jsonify({'error': 'Only users can add vehicles'}), 403
    
    data = request.get_json()
    marca = data.get('marca')
    modello = data.get('modello')
    targa = data.get('targa')
    
    if not all([marca, modello, targa]):
        return jsonify({'error': 'Marca, modello e targa sono obbligatori'}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = conn.cursor()
        
        # Verifica se la targa esiste già
        cursor.execute("SELECT id_veicolo FROM veicoli WHERE targa = %s", (targa,))
        if cursor.fetchone():
            return jsonify({'error': 'Targa già registrata'}), 400
        
        cursor.execute("""
            INSERT INTO veicoli (id_utente, marca, modello, targa)
            VALUES (%s, %s, %s, %s)
        """, (session['user_id'], marca, modello, targa))
        
        conn.commit()
        logger.info(f"New vehicle added by user {session['user_id']}")
        return jsonify({'message': 'Veicolo aggiunto con successo'})
        
    except Error as e:
        conn.rollback()
        logger.error(f"Error adding vehicle: {e}")
        return jsonify({'error': 'Database error: ' + str(e)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        conn.close()

# ========== ROUTE PRINCIPALE ==========

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/<path:path>')
def catch_all(path):
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)