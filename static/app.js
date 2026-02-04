let ready = false;

async function uploadPDF() {
  const file = document.getElementById("fileInput").files[0];
  if (!file) return alert("Choose a PDF");

  const formData = new FormData();
  formData.append("file", file);

  const status = document.getElementById("status");
  status.innerText = "Uploading...";
  status.className = "status loading";

  const res = await fetch("/upload", {
    method: "POST",
    body: formData
  });

  const data = await res.json();

  if (data.stored_in_database) {
    ready = true;
    status.innerText = "✅ Ready to chat";
    status.className = "status ready";
  } else {
    status.innerText = "Upload failed";
  }
}

async function askQuestion() {
  if (!ready) return alert("Upload PDF first!");

  const input = document.getElementById("questionInput");
  const q = input.value.trim();
  if (!q) return;

  addMessage(q, "user");
  input.value = "";

  const res = await fetch("/ask", {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({ question: q })
  });

  const data = await res.json();
  addMessage(data.answer, "ai");
}

function addMessage(text, type) {
  const box = document.getElementById("chatBox");
  const div = document.createElement("div");
  div.className = `msg ${type}`;
  div.innerText = text;
  box.appendChild(div);
  box.scrollTop = box.scrollHeight;
}
