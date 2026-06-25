const chatBody = document.getElementById("chatBody");
const input = document.getElementById("msgInput");

function sendMessage() {
  const text = input.value.trim();
  if (!text) return;

  fetch("/send-message", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      item_id: ITEM_ID,
      message: text,
    }),
  });

  input.value = "";
}

setInterval(() => {
  fetch("/get-messages/" + ITEM_ID)
    .then((res) => res.json())
    .then((data) => {
      chatBody.innerHTML = "";
      data.forEach((m) => {
        const div = document.createElement("div");
        div.className = "msg " + (m.is_me ? "right" : "left");
        div.innerText = m.message;
        chatBody.appendChild(div);
      });
    });
}, 3000);
