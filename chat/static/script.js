// --- Chat bubble templates ---
const userChatDiv = (message) => `
  <div class="flex gap-1 justify-end mt-3">
    <p class="bg-gradient-to-tr from-[#2731DC] to-[#03C1FC] py-2 px-3 text-lg text-white shadow-md rounded-br-3xl rounded-l-3xl w-fit max-w-[90%] md:max-w-[60%]">
      ${message}
    </p>
    <img src="/static/user.jpg" class="w-6 h-6 rounded-full ml-2 mb-1" alt="User"/>
  </div>
`;

const aiChatDiv = (message) => `
  <div class="flex gap-1 justify-start mt-3">
    <img src="/static/chat-bot.jpg" class="w-6 h-6 rounded-full ml-2 mb-1" alt="AI"/>
    <p class="bg-gray-100 py-2 px-3 text-lg text-gray-600 shadow-md rounded-bl-3xl rounded-r-3xl w-fit max-w-[90%] md:max-w-[60%]">
      ${message}
    </p>
  </div>
`;

const aiTypingDiv = () => `
  <div id="ai-typing" class="flex gap-1 justify-start mt-3">
    <img src="/static/chat-bot.jpg" class="w-6 h-6 rounded-full ml-2 mb-1" alt="AI"/>
    <p class="bg-gray-100 py-2 px-3 text-lg text-gray-600 shadow-md rounded-bl-3xl rounded-r-3xl w-fit max-w-[90%] md:max-w-[60%] animate-pulse">
      Typing...
    </p>
  </div>
`;

// --- DOM elements ---
const userMessage = document.getElementById("message");
const chatContainer = document.getElementById("chat-container");
const chatForm = document.getElementById("chat-form");

// --- Helper function: Get CSRF Token ---
function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(";").shift();
  return null;
}

// --- Auto-resize textarea ---
userMessage.addEventListener("input", () => {
  userMessage.style.height = "auto";
  userMessage.style.height = userMessage.scrollHeight + "px";
});

// --- Chat submission ---
let isSending = false;

async function handleSubmit(event) {
  event.preventDefault();
  if (isSending) return;

  const userPrompt = userMessage.value.trim();
  if (!userPrompt) return;

  // Add user chat bubble
  chatContainer.insertAdjacentHTML("beforeend", userChatDiv(userPrompt));
  userMessage.value = "";
  chatContainer.scrollTop = chatContainer.scrollHeight;

  // Add "Typing..." indicator
  chatContainer.insertAdjacentHTML("beforeend", aiTypingDiv());
  chatContainer.scrollTop = chatContainer.scrollHeight;

  const csrfToken = getCookie("csrftoken");
  isSending = true;

  try {
    const response = await fetch("/get_chatbot_response/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken,
      },
      body: JSON.stringify({ message: userPrompt }),
    });

    if (!response.ok) {
      throw new Error(`Server returned ${response.status}`);
    }

    const data = await response.json();
    const reply = data.reply || "Sorry, I could not respond. Try again!";

    document.getElementById("ai-typing")?.remove();

    chatContainer.insertAdjacentHTML("beforeend", aiChatDiv(reply));
    chatContainer.scrollTop = chatContainer.scrollHeight;
  } catch (error) {
    console.error("Error fetching chatbot response:", error);
    document.getElementById("ai-typing")?.remove();
    chatContainer.insertAdjacentHTML(
      "beforeend",
      aiChatDiv("Error: Unable to get response. Please try again.")
    );
    chatContainer.scrollTop = chatContainer.scrollHeight;
  } finally {
    isSending = false;
  }
}

// --- Event listeners ---
chatForm.addEventListener("submit", handleSubmit);
userMessage.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    handleSubmit(event);
  }
});
