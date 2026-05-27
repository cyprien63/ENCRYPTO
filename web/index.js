// --- V3 NEURAL STATE ---
let currentViewId = 'view-main';
let currentFileMode = 'encrypt'; 
let loadedFileInfo = null;
let cryptoFileInfo = null; 
let animRunning = false;
let progressValue = 0;
let hoverTimeout = null;

// DOM Elements
const views = {
    main: document.getElementById('view-main'),
    details: document.getElementById('view-details'),
    anim: document.getElementById('view-anim'),
    done: document.getElementById('view-done')
};

const titlebar = {
    startOver: document.getElementById('btn-start-over'),
    minimize: document.getElementById('btn-minimize'),
    close: document.getElementById('btn-close')
};

// --- NAVIGATION & VIEW TRANSITIONS ---
function switchView(viewId) {
    const currentView = document.getElementById(currentViewId);
    
    // Smooth exit
    currentView.classList.remove('active');
    
    setTimeout(() => {
        const nextView = document.getElementById(viewId);
        nextView.classList.add('active');
        currentViewId = viewId;
        
        // Titlebar logic
        if (viewId === 'view-done') {
            titlebar.startOver.classList.remove('hidden');
        } else {
            titlebar.startOver.classList.add('hidden');
        }
    }, 200); 
}

// Reset app back to initial main view state
function resetToMain() {
    loadedFileInfo = null;
    cryptoFileInfo = null;
    progressValue = 0;
    
    if (hoverTimeout) clearTimeout(hoverTimeout);
    
    // Clear inputs
    document.getElementById('input-password').value = '';
    document.getElementById('input-hint').value = '';
    document.getElementById('btn-toggle-password').textContent = 'Show';
    document.getElementById('input-password').type = 'password';
    
    // Toggle dropzone default state back smoothly
    document.getElementById('drop-default').classList.add('active');
    document.getElementById('drop-choice').classList.remove('active');
    document.getElementById('footer-instruction').textContent = 'Drop or Add Files or Folders to Get Started';
    
    switchView('view-main');
}

// --- TITLEBAR INTERACTIONS ---
titlebar.minimize.addEventListener('click', () => {
    if (window.pywebview) window.pywebview.api.minimize_window();
});

titlebar.close.addEventListener('click', () => {
    if (window.pywebview) window.pywebview.api.close_window();
});

titlebar.startOver.addEventListener('click', resetToMain);


// --- VIEW 1: DRAG & DROP & SELECT ---
const dropZone = document.getElementById('drop-zone');

['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
    dropZone.addEventListener(eventName, e => {
        e.preventDefault();
        e.stopPropagation();
    }, false);
});

// Hover Reveal Logic - Toggles based on mouse presence
dropZone.addEventListener('mouseenter', () => {
    if (hoverTimeout) clearTimeout(hoverTimeout);
    if (document.getElementById('drop-default').classList.contains('active')) {
        toggleDropChoiceState();
    }
});

dropZone.addEventListener('mouseleave', () => {
    // Only revert if we haven't actually loaded a file yet
    if (!loadedFileInfo && currentViewId === 'view-main') {
        hoverTimeout = setTimeout(() => {
            document.getElementById('drop-default').classList.add('active');
            document.getElementById('drop-choice').classList.remove('active');
            document.getElementById('footer-instruction').textContent = 'Drop or Add Files or Folders to Get Started';
        }, 300); // Quick revert for a snappy feel
    }
});

function toggleDropChoiceState() {
    document.getElementById('drop-default').classList.remove('active');
    document.getElementById('drop-choice').classList.add('active');
    document.getElementById('footer-instruction').textContent = "Select your target type to encrypt/decrypt";
}

// Drop handler
dropZone.addEventListener('drop', (e) => {
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        const file = files[0];
        if (file.path) {
            handlePathSelected(file.path);
        } else {
            readFileAndSend(file);
        }
    }
});

function readFileAndSend(file) {
    const reader = new FileReader();
    reader.onload = function(ev) {
        const base64 = ev.target.result.split(',')[1];
        if (window.pywebview) {
            window.pywebview.api.load_file_from_js(file.name, base64).then(handlePathResult);
        }
    };
    reader.readAsDataURL(file);
}

document.getElementById('btn-add-file').addEventListener('click', (e) => {
    e.stopPropagation();
    if (window.pywebview) {
        window.pywebview.api.select_file().then(handlePathResult);
    }
});

document.getElementById('btn-add-folder').addEventListener('click', (e) => {
    e.stopPropagation();
    if (window.pywebview) {
        window.pywebview.api.select_folder().then(handlePathResult);
    }
});

function handlePathSelected(path) {
    if (window.pywebview) window.pywebview.api.load_path_info(path).then(handlePathResult);
}

function handlePathResult(info) {
    if (!info || info.error) {
        if (info && info.error) alert(info.error);
        resetToMain();
        return;
    }
    
    loadedFileInfo = info;
    if (info.isCryptoFile) {
        currentFileMode = 'decrypt';
        window.pywebview.api.inspect_crypto_file(info.path).then(cryptoInfo => {
            cryptoFileInfo = (cryptoInfo && !cryptoInfo.error) ? cryptoInfo : null;
            setupDetailsView(cryptoFileInfo ? cryptoFileInfo.name : info.name, info.size, cryptoFileInfo ? cryptoFileInfo.isFolder : info.isFolder);
        });
    } else {
        currentFileMode = 'encrypt';
        setupDetailsView(info.name, info.size, info.isFolder);
    }
}

// --- ICON SYSTEM (3D MODELED) ---
function getFileIcon(name, isFolder) {
    if (isFolder) return `<div class="icon-container-3d"><div class="folder-3d"></div></div>`;
    
    // Extract extension
    const parts = name.toLowerCase().split('.');
    let ext = parts.pop();
    if (ext === 'gz' && parts[parts.length-1] === 'tar') ext = 'tar.gz';
    
    const libEntry = ICON_LIBRARY[ext] || {
        color: "#ffffff",
        label: ext.toUpperCase().substring(0, 6),
        icon: `<path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><polyline points="13 2 13 9 20 9"/>`
    };

    return `
        <div class="icon-container-3d">
            <div class="file-card-3d" style="--theme-color: ${libEntry.color};">
                <div class="card-face">
                    <div class="card-ext-label" style="z-index:10; font-size:13px; font-weight:900; color: ${libEntry.color}; text-shadow: 0 0 15px ${libEntry.color}, 0 0 5px #000;">${libEntry.label}</div>
                    <svg class="card-icon-svg" viewBox="0 0 24 24" fill="none" stroke="${libEntry.color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:32px; height:32px; filter: drop-shadow(0 0 10px ${libEntry.color});">
                        ${libEntry.icon}
                    </svg>
                    <div style="width: 20px; height: 2px; background: ${libEntry.color}; opacity: 0.5; border-radius: 1px; box-shadow: 0 0 10px ${libEntry.color};"></div>
                </div>
            </div>
        </div>
    `;
}

// --- VIEW 2: DETAILS SETUP ---
function setupDetailsView(name, size, isFolder) {
    document.getElementById('details-name').textContent = name;
    document.getElementById('details-size').textContent = size;
    
    const iconWrapper = document.getElementById('details-icon-wrapper');
    iconWrapper.innerHTML = getFileIcon(name, isFolder);
    
    const actionBtn = document.getElementById('btn-action-primary');
    const passwordInput = document.getElementById('input-password');
    const hintField = document.querySelector('.hint-field');
    const dividerH = document.querySelector('.divider-h');
    
    passwordInput.value = '';
    passwordInput.style.border = 'none';
    
    if (currentFileMode === 'decrypt') {
        actionBtn.textContent = 'Decrypt Now';
        hintField.classList.add('hidden');
        dividerH.classList.add('hidden');
        passwordInput.placeholder = (cryptoFileInfo && cryptoFileInfo.hint) ? `Password (Hint: ${cryptoFileInfo.hint})` : "Password";
    } else {
        actionBtn.textContent = 'Encrypt Now';
        hintField.classList.remove('hidden');
        dividerH.classList.remove('hidden');
        passwordInput.placeholder = "Password";
        document.getElementById('input-hint').value = '';
    }
    
    switchView('view-details');
}

document.getElementById('btn-toggle-password').addEventListener('click', (e) => {
    e.preventDefault();
    const input = document.getElementById('input-password');
    const btn = document.getElementById('btn-toggle-password');
    if (input.type === 'password') {
        input.type = 'text';
        btn.textContent = 'Hide';
    } else {
        input.type = 'password';
        btn.textContent = 'Show';
    }
});

document.getElementById('btn-cancel-details').addEventListener('click', resetToMain);

document.getElementById('btn-action-primary').addEventListener('click', () => {
    const password = document.getElementById('input-password').value;
    const hint = document.getElementById('input-hint').value;
    
    if (!password) {
        document.getElementById('input-password').style.border = '1px solid rgba(0,0,0,0.2)';
        return;
    }
    
    document.getElementById('anim-filename').textContent = loadedFileInfo.name;
    document.getElementById('anim-subtitle').textContent = currentFileMode === 'encrypt' ? 'SECURE ENCRYPTING' : 'SECURE DECRYPTING';
    document.getElementById('progress-percent').textContent = '0%';
    
    const scanGraphic = document.getElementById('scanner-icon-graphic');
    const isFolder = currentFileMode === 'encrypt' ? loadedFileInfo.isFolder : cryptoFileInfo.isFolder;
    scanGraphic.innerHTML = getFileIcon(loadedFileInfo.name, isFolder);
    
    // Add glowing pulse to icon during scan
    scanGraphic.style.animation = "pulse-glow 1.5s infinite alternate";
    
    switchView('view-anim');
    // Delay animation start to ensure view is visible and has dimensions
    setTimeout(startAnimations, 250);
    
    if (currentFileMode === 'encrypt') window.pywebview.api.encrypt_target(password, hint);
    else window.pywebview.api.decrypt_target(password);
});

// --- VIEW 3: NEURAL NETWORK ANIMATION ENGINE (V3) ---
const cvsChars = document.getElementById('canvas-chars');
const cvsSparks = document.getElementById('canvas-sparks');
let ctxChars = null, ctxSparks = null;
let nodes = [], scannerBarY = 0, scannerDirection = 1;

function resizeCanvases() {
    const container = document.querySelector('.anim-container');
    if (!container) return;
    const w = container.clientWidth || 360, h = container.clientHeight || 240;
    cvsChars.width = cvsSparks.width = w; cvsChars.height = cvsSparks.height = h;
    ctxChars = cvsChars.getContext('2d'); ctxSparks = cvsSparks.getContext('2d');
    
    // Initialize Neural Nodes
    nodes = Array.from({length: 40}, () => ({
        x: Math.random() * w, y: Math.random() * h,
        vx: (Math.random() - 0.5) * 0.5, vy: (Math.random() - 0.5) * 0.5,
        radius: Math.random() * 2 + 1
    }));
}

function startAnimations() {
    animRunning = true; resizeCanvases();
    [50, 200, 500].forEach(d => setTimeout(() => { if (animRunning) resizeCanvases(); }, d));
    requestAnimationFrame(animationLoop);
}

function animationLoop() {
    if (!animRunning || !ctxChars || !ctxSparks) return;
    const w = cvsChars.width, h = cvsChars.height;
    
    // 1. Neural Network Rendering
    ctxChars.clearRect(0, 0, w, h);
    ctxChars.strokeStyle = 'rgba(243, 200, 69, 0.15)';
    ctxChars.fillStyle = 'rgba(243, 200, 69, 0.5)';
    
    nodes.forEach((n, i) => {
        n.x += n.vx; n.y += n.vy;
        if (n.x < 0 || n.x > w) n.vx *= -1;
        if (n.y < 0 || n.y > h) n.vy *= -1;
        
        ctxChars.beginPath();
        ctxChars.arc(n.x, n.y, n.radius, 0, Math.PI * 2);
        ctxChars.fill();
        
        for (let j = i + 1; j < nodes.length; j++) {
            const m = nodes[j];
            const dist = Math.hypot(n.x - m.x, n.y - m.y);
            if (dist < 80) {
                ctxChars.lineWidth = 1 - dist/80;
                ctxChars.beginPath();
                ctxChars.moveTo(n.x, n.y);
                ctxChars.lineTo(m.x, m.y);
                ctxChars.stroke();
            }
        }
    });
    
    // 3. Digital Bursts
    ctxSparks.clearRect(0, 0, w, h);
    if (Math.random() < 0.2) {
        ctxSparks.fillStyle = 'rgba(243, 200, 69, 0.3)';
        ctxSparks.fillRect(0, Math.random() * h, w, 2); // Random bursts instead of tracked bar
    }
    
    requestAnimationFrame(animationLoop);
}

document.getElementById('btn-stop-anim').addEventListener('click', () => { animRunning = false; resetToMain(); });

// --- BACKEND CALLBACKS ---
window.onProgress = p => document.getElementById('progress-percent').textContent = `${p}%`;

window.onEncryptionComplete = (name, isFolder) => {
    animRunning = false;
    const baseName = loadedFileInfo.name.split('.').slice(0, -1).join('.') || loadedFileInfo.name;
    document.getElementById('done-name').textContent = baseName + ".crypto";
    document.getElementById('done-icon-wrapper').innerHTML = getFileIcon(baseName + ".crypto", false);
    loadedFileInfo.saveMode = 'encrypt';
    switchView('view-done');
};

window.onDecryptionComplete = (name, isFolder) => {
    animRunning = false;
    document.getElementById('done-name').textContent = name;
    document.getElementById('done-icon-wrapper').innerHTML = getFileIcon(name, isFolder);
    loadedFileInfo.saveMode = 'decrypt';
    switchView('view-done');
};

window.onDecryptionFailed = () => {
    animRunning = false; switchView('view-details');
    const input = document.getElementById('input-password');
    input.value = ''; input.style.border = '2px solid rgba(255,0,0,0.3)';
    input.placeholder = (cryptoFileInfo && cryptoFileInfo.hint) ? `Incorrect. Hint: ${cryptoFileInfo.hint}` : "Incorrect Password";
};

window.onOperationError = msg => { animRunning = false; alert(`Error: ${msg}`); resetToMain(); };

document.getElementById('btn-save-as').addEventListener('click', () => {
    if (window.pywebview && loadedFileInfo) {
        window.pywebview.api.save_output(loadedFileInfo.saveMode).then(res => {
            if (res && res.success) resetToMain();
            else if (res && res.error) alert(`Save Error: ${res.error}`);
        });
    }
});

window.addEventListener('resize', () => { if (animRunning) resizeCanvases(); });
window.addEventListener('DOMContentLoaded', resetToMain);
