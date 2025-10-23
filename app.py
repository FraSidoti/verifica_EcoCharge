from flask import Flask, request, jsonify, session, render_template
from flask_cors import CORS
import mysql.connector
from mysql.connector import Error
import bcrypt
import jwt
import datetime
from functools import wraps
import json
from math import radians, sin, cos, sqrt, atan2

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'
CORS(app, supports_credentials=True)

# Configurazione database
DB_CONFIG = {
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
        print(f"Error connecting to MySQL: {e}")
        return None

# Decorator per l'autenticazione
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function

# Decorator per admin only
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('user_type') != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated_function

# Routes per l'autenticazione
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
        
        if admin and bcrypt.checkpw(password.encode('utf-8'), admin['password_hash'].encode('utf-8')):
            session['user_id'] = admin['id_admin']
            session['user_type'] = 'admin'
            session['email'] = admin['email']
            session['name'] = f"{admin['nome']} {admin['cognome']}"
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
        
        if user and bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
            session['user_id'] = user['id_utente']
            session['user_type'] = 'user'
            session['email'] = user['email']
            session['name'] = f"{user['nome']} {user['cognome']}"
            return jsonify({
                'message': 'Login successful',
                'user_type': 'user',
                'user': {
                    'id': user['id_utente'],
                    'email': user['email'],
                    'name': f"{user['nome']} {user['cognome']}"
                }
            })
        
        return jsonify({'error': 'Invalid credentials'}), 401
        
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
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
        return jsonify({'error': 'All fields are required'}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = conn.cursor()
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        cursor.execute("""
            INSERT INTO utenti (email, password_hash, nome, cognome, telefono, indirizzo, citta)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (email, password_hash, nome, cognome, telefono, indirizzo, citta))
        
        conn.commit()
        return jsonify({'message': 'Registration successful'})
        
    except Error as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# Routes per le colonnine
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
                   AVG(r.energia_kwh) as energia_media
            FROM colonnine c
            LEFT JOIN ricariche r ON c.id_colonnina = r.id_colonnina
            GROUP BY c.id_colonnina
        """)
        colonnine = cursor.fetchall()
        
        # Classifica l'utilizzo
        for colonnina in colonnine:
            utilizzi = colonnina['utilizzi_totali'] or 0
            if utilizzi < 10:
                colonnina['classificazione'] = 'basso'
            elif utilizzi < 30:
                colonnina['classificazione'] = 'medio'
            else:
                colonnina['classificazione'] = 'alto'
        
        return jsonify(colonnine)
        
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
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
        return jsonify({'error': 'All fields are required'}), 400
    
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
        return jsonify({'message': 'Colonnina added successfully'})
        
    except Error as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# Routes per le prenotazioni
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
        return jsonify({'error': 'All fields are required'}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = conn.cursor()
        
        # Verifica che il veicolo appartenga all'utente
        cursor.execute("SELECT id_utente FROM veicoli WHERE id_veicolo = %s", (id_veicolo,))
        veicolo = cursor.fetchone()
        
        if not veicolo or veicolo[0] != session['user_id']:
            return jsonify({'error': 'Invalid vehicle'}), 400
        
        # Verifica che la colonnina sia disponibile
        cursor.execute("""
            SELECT * FROM ricariche 
            WHERE id_colonnina = %s 
            AND ((data_ora_inizio BETWEEN %s AND %s) OR (data_ora_fine BETWEEN %s AND %s))
        """, (id_colonnina, data_ora_inizio, data_ora_fine, data_ora_inizio, data_ora_fine))
        
        if cursor.fetchone():
            return jsonify({'error': 'Colonnina not available in this time slot'}), 400
        
        cursor.execute("""
            INSERT INTO ricariche (id_utente, id_veicolo, id_colonnina, data_ora_inizio, data_ora_fine, energia_kwh)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (session['user_id'], id_veicolo, id_colonnina, data_ora_inizio, data_ora_fine, energia_kwh))
        
        conn.commit()
        return jsonify({'message': 'Reservation created successfully'})
        
    except Error as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
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
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# Routes per gli amministratori
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
        return jsonify({'error': 'All fields are required'}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = conn.cursor()
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        cursor.execute("""
            INSERT INTO utenti (email, password_hash, nome, cognome, telefono, indirizzo, citta)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (email, password_hash, nome, cognome, telefono, indirizzo, citta))
        
        conn.commit()
        return jsonify({'message': 'User added successfully'})
        
    except Error as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
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
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)