// Configuration
const API_BASE = '';

// State management
let currentUser = null;
let map = null;
let markers = [];
let colonnine = [];
let veicoli = [];

// Map initialization
function initMap() {
    map = L.map('map').setView([41.9028, 12.4964], 6);
    
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
    }).addTo(map);
    
    loadColonnine();
}

// Authentication functions
async function login() {
    const email = document.getElementById('login-email').value;
    const password = document.getElementById('login-password').value;
    
    if (!email || !password) {
        showAlert('Inserisci email e password', 'danger');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/api/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password }),
            credentials: 'include'
        });
        
        const data = await response.json();
        
        if (response.ok) {
            currentUser = data.user;
            showAlert('Login effettuato con successo!', 'success');
            updateUI();
            loadColonnine();
            resetLoginForm();
        } else {
            showAlert(data.error, 'danger');
        }
    } catch (error) {
        console.error('Login error:', error);
        showAlert('Errore di connessione', 'danger');
    }
}

async function register() {
    const formData = {
        email: document.getElementById('reg-email').value,
        password: document.getElementById('reg-password').value,
        nome: document.getElementById('reg-nome').value,
        cognome: document.getElementById('reg-cognome').value,
        telefono: document.getElementById('reg-telefono').value,
        indirizzo: document.getElementById('reg-indirizzo').value,
        citta: document.getElementById('reg-citta').value
    };
    
    if (!formData.email || !formData.password || !formData.nome || !formData.cognome) {
        showAlert('Compila tutti i campi obbligatori', 'danger');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/api/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(formData),
            credentials: 'include'
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showAlert('Registrazione completata! Ora puoi effettuare il login.', 'success');
            showLogin();
            resetRegisterForm();
        } else {
            showAlert(data.error, 'danger');
        }
    } catch (error) {
        console.error('Registration error:', error);
        showAlert('Errore di connessione', 'danger');
    }
}

async function logout() {
    try {
        const response = await fetch(`${API_BASE}/api/logout`, {
            method: 'POST',
            credentials: 'include'
        });
        
        if (response.ok) {
            currentUser = null;
            showAlert('Logout effettuato', 'info');
            updateUI();
            loadColonnine();
        }
    } catch (error) {
        console.error('Logout error:', error);
        showAlert('Errore durante il logout', 'danger');
    }
}

async function checkAuth() {
    try {
        const response = await fetch(`${API_BASE}/api/check-auth`, {
            credentials: 'include'
        });
        
        const data = await response.json();
        
        if (data.authenticated) {
            currentUser = data.user;
            updateUI();
        }
    } catch (error) {
        console.error('Auth check error:', error);
    }
}

// Colonnine management
async function loadColonnine() {
    try {
        showLoading('colonnine-list');
        
        const response = await fetch(`${API_BASE}/api/colonnine`, {
            credentials: 'include'
        });
        
        if (!response.ok) throw new Error('Network error');
        
        colonnine = await response.json();
        updateMapMarkers();
        updateColonnineList();
        
    } catch (error) {
        console.error('Error loading colonnine:', error);
        showAlert('Errore nel caricamento delle colonnine', 'danger');
    }
}

function updateMapMarkers() {
    // Remove existing markers
    markers.forEach(marker => map.removeLayer(marker));
    markers = [];
    
    // Add new markers
    colonnine.forEach(colonnina => {
        const icon = getColonninaIcon(colonnina.classificazione);
        
        const marker = L.marker([colonnina.latitudine, colonnina.longitudine], { icon })
            .addTo(map)
            .bindPopup(createColonninaPopup(colonnina));
        
        markers.push(marker);
    });
    
    // Adjust map view if there are colonnine
    if (colonnine.length > 0) {
        const group = new L.featureGroup(markers);
        map.fitBounds(group.getBounds().pad(0.1));
    }
}

function getColonninaIcon(classificazione) {
    const color = {
        'nessuno': 'gray',
        'basso': 'green',
        'medio': 'orange',
        'alto': 'red'
    }[classificazione] || 'blue';
    
    return L.divIcon({
        html: `<div style="background-color: ${color}; width: 20px; height: 20px; border-radius: 50%; border: 2px solid white;"></div>`,
        className: 'colonnina-marker',
        iconSize: [24, 24]
    });
}

function createColonninaPopup(colonnina) {
    return `
        <div class="colonnina-popup">
            <h6><strong>${colonnina.indirizzo}</strong></h6>
            <p><strong>Potenza:</strong> ${colonnina.potenza_kw} kW</p>
            <p><strong>Utilizzi totali:</strong> ${colonnina.utilizzi_totali || 0}</p>
            <p><strong>Classificazione:</strong> 
                <span class="badge bg-${getClassificazioneBadgeColor(colonnina.classificazione)}">
                    ${colonnina.classificazione}
                </span>
            </p>
            ${colonnina.nil ? `<p><strong>NIL:</strong> ${colonnina.nil}</p>` : ''}
            ${currentUser && currentUser.user_type === 'user' ? 
                `<button class="btn btn-sm btn-primary mt-2" onclick="prenotaColonnina(${colonnina.id_colonnina})">
                    Prenota
                </button>` : ''}
        </div>
    `;
}

function getClassificazioneBadgeColor(classificazione) {
    const colors = {
        'nessuno': 'secondary',
        'basso': 'success',
        'medio': 'warning',
        'alto': 'danger'
    };
    return colors[classificazione] || 'primary';
}

function updateColonnineList() {
    const container = document.getElementById('colonnine-list');
    
    if (colonnine.length === 0) {
        container.innerHTML = '<div class="alert alert-info">Nessuna colonnina disponibile</div>';
        return;
    }
    
    container.innerHTML = `
        <h4>Colonnine di Ricarica (${colonnine.length})</h4>
        <div class="row" id="colonnine-cards"></div>
    `;
    
    const cardsContainer = document.getElementById('colonnine-cards');
    
    colonnine.forEach(colonnina => {
        const card = document.createElement('div');
        card.className = 'col-md-6 mb-3';
        card.innerHTML = `
            <div class="card h-100">
                <div class="card-body">
                    <h6 class="card-title">${colonnina.indirizzo}</h6>
                    <p class="card-text">
                        <small class="text-muted">
                            <strong>Potenza:</strong> ${colonnina.potenza_kw} kW<br>
                            <strong>Utilizzi:</strong> ${colonnina.utilizzi_totali || 0}<br>
                            <strong>Classificazione:</strong> 
                            <span class="badge bg-${getClassificazioneBadgeColor(colonnina.classificazione)}">
                                ${colonnina.classificazione}
                            </span>
                        </small>
                    </p>
                </div>
                ${currentUser && currentUser.user_type === 'user' ? `
                    <div class="card-footer">
                        <button class="btn btn-sm btn-primary w-100" onclick="prenotaColonnina(${colonnina.id_colonnina})">
                            Prenota
                        </button>
                    </div>
                ` : ''}
            </div>
        `;
        cardsContainer.appendChild(card);
    });
}

// Admin functions
async function addColonnina() {
    const formData = {
        indirizzo: document.getElementById('colonnina-indirizzo').value,
        latitudine: parseFloat(document.getElementById('colonnina-lat').value),
        longitudine: parseFloat(document.getElementById('colonnina-lng').value),
        potenza_kw: parseFloat(document.getElementById('colonnina-potenza').value),
        nil: document.getElementById('colonnina-nil').value
    };
    
    if (!formData.indirizzo || !formData.latitudine || !formData.longitudine || !formData.potenza_kw) {
        showAlert('Compila tutti i campi obbligatori', 'danger');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/api/colonnine`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(formData),
            credentials: 'include'
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showAlert('Colonnina aggiunta con successo!', 'success');
            bootstrap.Modal.getInstance(document.getElementById('addColonninaModal')).hide();
            resetColonninaForm();
            loadColonnine();
        } else {
            showAlert(data.error, 'danger');
        }
    } catch (error) {
        console.error('Error adding colonnina:', error);
        showAlert('Errore di connessione', 'danger');
    }
}

async function addUtente() {
    const formData = {
        email: document.getElementById('admin-email').value,
        password: document.getElementById('admin-password').value,
        nome: document.getElementById('admin-nome').value,
        cognome: document.getElementById('admin-cognome').value,
        telefono: document.getElementById('admin-telefono').value,
        indirizzo: document.getElementById('admin-indirizzo').value,
        citta: document.getElementById('admin-citta').value
    };
    
    if (!formData.email || !formData.password || !formData.nome || !formData.cognome) {
        showAlert('Compila tutti i campi obbligatori', 'danger');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/api/admin/utenti`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(formData),
            credentials: 'include'
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showAlert('Utente aggiunto con successo!', 'success');
            bootstrap.Modal.getInstance(document.getElementById('addUtenteModal')).hide();
            resetUtenteForm();
        } else {
            showAlert(data.error, 'danger');
        }
    } catch (error) {
        console.error('Error adding user:', error);
        showAlert('Errore di connessione', 'danger');
    }
}

async function loadStatistiche() {
    try {
        showLoading('statistiche-section');
        
        const response = await fetch(`${API_BASE}/api/admin/statistiche`, {
            credentials: 'include'
        });
        
        if (!response.ok) throw new Error('Network error');
        
        const data = await response.json();
        displayStatistiche(data);
        
    } catch (error) {
        console.error('Error loading statistics:', error);
        showAlert('Errore nel caricamento delle statistiche', 'danger');
    }
}

function displayStatistiche(data) {
    const container = document.getElementById('statistiche-section');
    container.style.display = 'block';
    
    container.innerHTML = `
        <div class="row">
            <div class="col-12">
                <h4>Statistiche e Previsioni</h4>
                
                <div class="row mb-4">
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header">
                                <h5>Utilizzo Colonnine</h5>
                            </div>
                            <div class="card-body">
                                <canvas id="utilizzoChart" width="400" height="200"></canvas>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header">
                                <h5>Previsioni Mensili</h5>
                            </div>
                            <div class="card-body">
                                <canvas id="previsioniChart" width="400" height="200"></canvas>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="card">
                    <div class="card-header">
                        <h5>Dettaglio Colonnine</h5>
                    </div>
                    <div class="card-body">
                        <div class="table-responsive">
                            <table class="table table-striped">
                                <thead>
                                    <tr>
                                        <th>Indirizzo</th>
                                        <th>Utilizzi</th>
                                        <th>Energia Totale (kWh)</th>
                                        <th>Energia Media (kWh)</th>
                                        <th>Classificazione</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${data.stats_colonnine.map(colonnina => `
                                        <tr>
                                            <td>${colonnina.indirizzo}</td>
                                            <td>${colonnina.utilizzi || 0}</td>
                                            <td>${(colonnina.energia_totale || 0).toFixed(2)}</td>
                                            <td>${(colonnina.energia_media || 0).toFixed(2)}</td>
                                            <td>
                                                <span class="badge bg-${getClassificazioneBadgeColor(
                                                    colonnina.utilizzi < 5 ? 'basso' : 
                                                    colonnina.utilizzi < 15 ? 'medio' : 'alto'
                                                )}">
                                                    ${colonnina.utilizzi < 5 ? 'basso' : 
                                                      colonnina.utilizzi < 15 ? 'medio' : 'alto'}
                                                </span>
                                            </td>
                                        </tr>
                                    `).join('')}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    // Create charts
    createUtilizzoChart(data.stats_colonnine);
    createPrevisioniChart(data.previsioni);
}

function createUtilizzoChart(stats) {
    const ctx = document.getElementById('utilizzoChart').getContext('2d');
    const topColonnine = stats.slice(0, 8); // Show top 8
    
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: topColonnine.map(c => c.indirizzo.substring(0, 20) + '...'),
            datasets: [{
                label: 'Numero di Utilizzi',
                data: topColonnine.map(c => c.utilizzi || 0),
                backgroundColor: 'rgba(54, 162, 235, 0.5)',
                borderColor: 'rgba(54, 162, 235, 1)',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
}

function createPrevisioniChart(previsioni) {
    const ctx = document.getElementById('previsioniChart').getContext('2d');
    const mesi = ['Gen', 'Feb', 'Mar', 'Apr', 'Mag', 'Giu', 'Lug', 'Ago', 'Set', 'Ott', 'Nov', 'Dic'];
    
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: previsioni.map(p => mesi[p.mese - 1]),
            datasets: [{
                label: 'Prenotazioni',
                data: previsioni.map(p => p.prenotazioni),
                borderColor: 'rgba(255, 99, 132, 1)',
                backgroundColor: 'rgba(255, 99, 132, 0.1)',
                tension: 0.1
            }]
        },
        options: {
            responsive: true,
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
}

// User functions
async function loadVeicoli() {
    try {
        const response = await fetch(`${API_BASE}/api/veicoli`, {
            credentials: 'include'
        });
        
        if (!response.ok) throw new Error('Network error');
        
        veicoli = await response.json();
        updateVeicoliSelect();
        displayVeicoliList();
        
    } catch (error) {
        console.error('Error loading vehicles:', error);
        showAlert('Errore nel caricamento dei veicoli', 'danger');
    }
}

function updateVeicoliSelect() {
    const select = document.getElementById('prenota-veicolo');
    select.innerHTML = '<option value="">Seleziona veicolo</option>';
    
    veicoli.forEach(veicolo => {
        const option = document.createElement('option');
        option.value = veicolo.id_veicolo;
        option.textContent = `${veicolo.marca} ${veicolo.modello} (${veicolo.targa})`;
        select.appendChild(option);
    });
}

function displayVeicoliList() {
    const container = document.getElementById('veicoli-list');
    
    if (!veicoli.length) {
        container.innerHTML = '<div class="alert alert-info">Nessun veicolo registrato</div>';
        return;
    }
    
    container.innerHTML = `
        <h5>I Miei Veicoli</h5>
        <div class="row" id="veicoli-cards"></div>
    `;
    
    const cardsContainer = document.getElementById('veicoli-cards');
    
    veicoli.forEach(veicolo => {
        const card = document.createElement('div');
        card.className = 'col-md-6 mb-3';
        card.innerHTML = `
            <div class="card">
                <div class="card-body">
                    <h6 class="card-title">${veicolo.marca} ${veicolo.modello}</h6>
                    <p class="card-text">
                        <strong>Targa:</strong> ${veicolo.targa}<br>
                        <strong>Registrato il:</strong> ${new Date(veicolo.created_at).toLocaleDateString()}
                    </p>
                </div>
            </div>
        `;
        cardsContainer.appendChild(card);
    });
}

function prenotaColonnina(idColonnina) {
    if (!currentUser || currentUser.user_type !== 'user') {
        showAlert('Devi essere un utente registrato per prenotare', 'warning');
        return;
    }
    
    // Set the colonnina in the form
    document.getElementById('prenota-colonnina').value = idColonnina;
    
    // Load vehicles and show modal
    loadVeicoli();
    
    const modal = new bootstrap.Modal(document.getElementById('prenotaModal'));
    modal.show();
}

async function createPrenotazione() {
    const formData = {
        id_veicolo: parseInt(document.getElementById('prenota-veicolo').value),
        id_colonnina: parseInt(document.getElementById('prenota-colonnina').value),
        data_ora_inizio: document.getElementById('prenota-inizio').value,
        data_ora_fine: document.getElementById('prenota-fine').value,
        energia_kwh: parseFloat(document.getElementById('prenota-energia').value)
    };
    
    // Validation
    if (!formData.id_veicolo || !formData.id_colonnina || !formData.data_ora_inizio || 
        !formData.data_ora_fine || !formData.energia_kwh) {
        showAlert('Compila tutti i campi', 'danger');
        return;
    }
    
    if (new Date(formData.data_ora_inizio) >= new Date(formData.data_ora_fine)) {
        showAlert('La data di fine deve essere successiva alla data di inizio', 'danger');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/api/prenotazioni`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(formData),
            credentials: 'include'
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showAlert('Prenotazione creata con successo!', 'success');
            bootstrap.Modal.getInstance(document.getElementById('prenotaModal')).hide();
            resetPrenotazioneForm();
        } else {
            showAlert(data.error, 'danger');
        }
    } catch (error) {
        console.error('Error creating reservation:', error);
        showAlert('Errore di connessione', 'danger');
    }
}

// UI Helper functions
function updateUI() {
    const authSection = document.getElementById('auth-section');
    const userInfo = document.getElementById('user-info');
    const adminPanel = document.getElementById('admin-panel');
    const userPanel = document.getElementById('user-panel');
    const statisticheSection = document.getElementById('statistiche-section');
    
    if (currentUser) {
        authSection.style.display = 'none';
        userInfo.style.display = 'block';
        document.getElementById('user-name').textContent = currentUser.name;
        document.getElementById('user-type').textContent = `Tipo: ${currentUser.user_type}`;
        
        if (currentUser.user_type === 'admin') {
            adminPanel.style.display = 'block';
            userPanel.style.display = 'none';
        } else {
            adminPanel.style.display = 'none';
            userPanel.style.display = 'block';
        }
        
        // Hide statistics when not in use
        statisticheSection.style.display = 'none';
    } else {
        authSection.style.display = 'block';
        userInfo.style.display = 'none';
        adminPanel.style.display = 'none';
        userPanel.style.display = 'none';
        statisticheSection.style.display = 'none';
    }
}

function showLogin() {
    document.getElementById('login-form').style.display = 'block';
    document.getElementById('register-form').style.display = 'none';
}

function showRegister() {
    document.getElementById('login-form').style.display = 'none';
    document.getElementById('register-form').style.display = 'block';
}

function showAlert(message, type) {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    const container = document.getElementById('alerts-container');
    container.appendChild(alertDiv);
    
    // Auto remove after 5 seconds
    setTimeout(() => {
        if (alertDiv.parentElement) {
            alertDiv.remove();
        }
    }, 5000);
}

function showLoading(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        element.innerHTML = `
            <div class="d-flex justify-content-center">
                <div class="spinner-border" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
            </div>
        `;
    }
}

// Form reset functions
function resetLoginForm() {
    document.getElementById('login-email').value = '';
    document.getElementById('login-password').value = '';
}

function resetRegisterForm() {
    document.getElementById('reg-email').value = '';
    document.getElementById('reg-password').value = '';
    document.getElementById('reg-nome').value = '';
    document.getElementById('reg-cognome').value = '';
    document.getElementById('reg-telefono').value = '';
    document.getElementById('reg-indirizzo').value = '';
    document.getElementById('reg-citta').value = '';
}

function resetColonninaForm() {
    document.getElementById('colonnina-indirizzo').value = '';
    document.getElementById('colonnina-lat').value = '';
    document.getElementById('colonnina-lng').value = '';
    document.getElementById('colonnina-potenza').value = '';
    document.getElementById('colonnina-nil').value = '';
}

function resetUtenteForm() {
    document.getElementById('admin-email').value = '';
    document.getElementById('admin-password').value = '';
    document.getElementById('admin-nome').value = '';
    document.getElementById('admin-cognome').value = '';
    document.getElementById('admin-telefono').value = '';
    document.getElementById('admin-indirizzo').value = '';
    document.getElementById('admin-citta').value = '';
}

function resetPrenotazioneForm() {
    document.getElementById('prenota-veicolo').value = '';
    document.getElementById('prenota-colonnina').value = '';
    document.getElementById('prenota-inizio').value = '';
    document.getElementById('prenota-fine').value = '';
    document.getElementById('prenota-energia').value = '';
}

// Set current location for new colonnina
function setCurrentLocation() {
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            position => {
                document.getElementById('colonnina-lat').value = position.coords.latitude.toFixed(6);
                document.getElementById('colonnina-lng').value = position.coords.longitude.toFixed(6);
            },
            error => {
                showAlert('Impossibile ottenere la posizione corrente', 'warning');
            }
        );
    } else {
        showAlert('Geolocalizzazione non supportata', 'warning');
    }
}

// Initialize application
document.addEventListener('DOMContentLoaded', function() {
    initMap();
    checkAuth();
    
    // Set current date/time for reservation form
    const now = new Date();
    const future = new Date(now.getTime() + 60 * 60 * 1000); // 1 hour from now
    
    document.getElementById('prenota-inizio').min = now.toISOString().slice(0, 16);
    document.getElementById('prenota-fine').min = future.toISOString().slice(0, 16);
});