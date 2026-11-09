const chatForm = document.getElementById("chatForm");
const chatInput = document.getElementById("chatInput");
const chatMessages = document.getElementById("chatMessages");

chatForm.addEventListener("submit", async function (event) {
    event.preventDefault();

    const message = chatInput.value.trim();

    if (!message) {
        return;
    }

    addMessage(message, "user-message");
    chatInput.value = "";

    try {
        const response = await fetch("/chatbot/message", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                message: message
            })
        });

        const data = await response.json();

        addMessage(data.reply, "bot-message");

    } catch (error) {
        addMessage(
            "Sorry, something went wrong. Please try again.",
            "bot-message"
        );
    }
});

function addMessage(message, className) {
    const messageElement = document.createElement("div");

    messageElement.className = className;
    messageElement.textContent = message;

    chatMessages.appendChild(messageElement);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}