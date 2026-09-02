let currentSubject = "pc";

function toggleBurger(open) {
    const drawer = document.getElementById("burgerDrawer");
    const overlay = document.getElementById("burgerOverlay");
    if (open) {
        drawer.classList.add("open");
        overlay.style.display = "block";
    } else {
        drawer.classList.remove("open");
        overlay.style.display = "none";
    }
}

async function maNouvelleConnexion() {
    const k = document.getElementById("userAccessKey").value.trim();
    if(!k) return;
    const res = await fetch("/api/login", { method:"POST", body: JSON.stringify({key: k}) });
    const data = await res.json();
    if(data.status === "success") {
        document.getElementById("welcomeScreen").style.display = "none";
        document.getElementById("chatScreen").style.display = "flex";
        document.getElementById("userEmailLabel").innerText = data.role === "admin" ? "Admin Node" : "Clé: " + k;
        document.getElementById("avatarLetter").innerText = data.role === "admin" ? "A" : k.charAt(0).toUpperCase();
    } else { 
        alert(data.message); 
    }
}

function selectSubject(subj) {
    currentSubject = subj;
    document.querySelectorAll(".nav-item").forEach(b => b.classList.remove("active"));
    document.getElementById("btn-" + subj).classList.add("active");
    document.getElementById("subjectIndicator").innerText = "Matière active : " + subj.toUpperCase();
    toggleBurger(false);
}

async function sendMessage() {
    const inp = document.getElementById("userInput");
    const val = inp.value.trim();
    if(!val) return;
    creerBulle(val, "student-user");
    inp.value = "";
    const wait = creerBulle("Thinking.", "system-ai");
    const res = await fetch("/api/chat", { method:"POST", body: JSON.stringify({question: val, subject: currentSubject}) });
    const data = await res.json();
    wait.innerText = data.response;
}

function creerBulle(txt, cls) {
    const box = document.getElementById("chatBox");
    const d = document.createElement("div");
    d.className = "log-bubble " + cls;
    d.innerText = txt;
    box.appendChild(d);
    box.scrollTop = box.scrollHeight;
    return d;
}
