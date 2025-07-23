// ============================================================================
// CHAT BOT CONFIGURATION
// ============================================================================

const sections = [
  {
    // 0 - Introduction from Mia
    messages: [
      {
        text: "Hi 👋 I'm Mia from CuraDebt—BBB A+ rated, helping lower payments and debt for 17+ years.",
        delay: 1000,
      },
      {
        text: "Just answer three quick questions to check eligibility… takes < 60 seconds.",
        delay: 1000,
      },
      {
        text: "Roughly how much debt are you carrying right now?",
        delay: 1000,
      },
      {
        delay: 0,
        selections: [
          {
            title: "$5,000 – $9,999",
            nextSectionIndex: 1,
          },
          {
            title: "$10,000 – $24,999",
            nextSectionIndex: 1,
          },
          {
            title: "$25,000+",
            nextSectionIndex: 1,
          },
        ],
      },
    ],
  },
  {
    // 1 - Type of debt
    messages: [
      {
        text: "Which expense hits hardest each month?",
        delay: 1000,
      },
      {
        delay: 0,
        selections: [
          {
            title: "Rent / mortgage",
            nextSectionIndex: 2,
          },
          {
            title: "Groceries / daycare",
            nextSectionIndex: 2,
          },
          {
            title: "Other",
            nextSectionIndex: 2,
          },
        ],
      },
    ],
  },
  {
    // 2 - How soon to act
    messages: [
      {
        text: "When would you like a lower payment to start?",
        delay: 1000,
      },
      {
        delay: 0,
        selections: [
          {
            title: "ASAP",
            nextSectionIndex: 3,
          },
          {
            title: "Next 2+ Months",
            nextSectionIndex: 3,
          },
        ],
      },
    ],
  },
  {
    // 3 - Congratulations and CTA
    messages: [
      {
        text: "Great. Based on what you shared, our program could <strong>lower your payment</strong> and potentially <strong>reduce what you owe</strong> by up to 30%.",
        delay: 1000,
      },
      {
        text: "Ready to see your new lower payment and how much you could save?",
        delay: 1000,
      },
      {
        delay: 1000,
        selections: [
          {
            title: "📱 Call Now To Claim Benefits",
            stBtn: "Call Now To Claim Benefits",
            nextSectionIndex: 4,
          },
          {
            title: "📅 Can't Talk Now - Request A Call Back",
            href: "https://www.curadebt.com/debtpps?a_=single-mom-debt-relief&b_fb" + window.location.search,
          },
        ],
      },
    ],
  },
  {
    // 4 - Call CTA
    messages: [
      {
        text: "Perfect! Let me connect you with a Senior Counselor right now to discuss your personalized debt relief plan.",
        delay: 1000,
      },
      {
        text: "📞 <strong>Call Now: 1-800-CURADEBT</strong><br><small>Available 24/7 - No wait time</small>",
        delay: 1000,
      },
      {
        delay: 1000,
        selections: [
          {
            title: "📱 Call Now To Claim Benefits",
            href: "tel:1-800-CURADEBT",
          },
          {
            title: "📅 Can't Talk Now - Request A Call Back",
            href: "https://www.curadebt.com/debtpps?a_=single-mom-debt-relief&b_fb" + window.location.search,
          },
        ],
      },
    ],
  },
];

// ============================================================================
// GLOBAL VARIABLES
// ============================================================================

let currentSectionIndex = 0;
let selectedDebtAmount = null;

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

function getCurrentTime() {
  const now = new Date();
  const hours = now.getHours().toString().padStart(2, "0");
  const minutes = now.getMinutes().toString().padStart(2, "0");
  return `${hours}:${minutes}`;
}

function scrollToBottom() {
  // Only scroll when new content would overflow the screen height
  setTimeout(() => {
    const chatContainer = document.getElementById("chatContainer");
    
    if (chatContainer) {
      const containerHeight = chatContainer.scrollHeight;
      const viewportHeight = window.innerHeight;
      const currentScrollTop = window.pageYOffset || document.documentElement.scrollTop;
      const chatTop = chatContainer.offsetTop;
      const chatBottom = chatTop + containerHeight;
      
      // Only scroll if the new content would overflow the visible area
      const visibleBottom = currentScrollTop + viewportHeight;
      
      if (chatBottom > visibleBottom) {
        window.scrollTo({
          top: chatBottom - viewportHeight + 100, // 100px padding from bottom
          behavior: 'smooth'
        });
      }
    }
  }, 150); // Small delay to ensure DOM updates are complete
}

function typingEffect() {
  return `
    <div class="typing-animation">
      <div class="typing-dot"></div>
      <div class="typing-dot"></div>
      <div class="typing-dot"></div>
    </div>
  `;
}


// ============================================================================
// MESSAGE CREATION FUNCTIONS
// ============================================================================

function createAgentBlock() {
  const agentBlock = document.createElement("div");
  agentBlock.className = "agent-container";

  const avatarContainer = document.createElement("div");
  avatarContainer.className = "agent-img avatar-container";

  const avatar = document.createElement("img");
  avatar.src = "./assets/agent.jpg";
  avatar.alt = "Mia Avatar";
  avatar.className = "w-8 h-8 rounded-full";

  avatarContainer.appendChild(avatar);
  agentBlock.appendChild(avatarContainer);

  const chatBubbleContainer = document.createElement("div");
  chatBubbleContainer.className = "agent-chat";
  agentBlock.appendChild(chatBubbleContainer);

  return { agentBlock, chatBubbleContainer };
}

// Function to position avatar at the last message-content (excluding typing animation)
function positionAvatarAtLastMessage(agentBlock) {
  const avatarContainer = agentBlock.querySelector('.agent-img');
  const messageContents = agentBlock.querySelectorAll('.message-content');
  
  if (avatarContainer && messageContents.length > 0) {
    const lastMessage = messageContents[messageContents.length - 1];
    const lastMessageRect = lastMessage.getBoundingClientRect();
    const agentChatRect = agentBlock.querySelector('.agent-chat').getBoundingClientRect();
    
    // Position avatar at the left of the last message
    const avatarTop = lastMessageRect.top - agentChatRect.top + (lastMessageRect.height / 2) - 20; // Center vertically on message
    avatarContainer.style.top = `${avatarTop}px`;
  }
}

// Function to position timestamp below the avatar
function positionTimestampAtLastMessage(agentBlock) {
  const timestampSpan = agentBlock.querySelector('.message-timestamp');
  const avatarContainer = agentBlock.querySelector('.agent-img');
  
  if (timestampSpan && avatarContainer) {
    const avatarRect = avatarContainer.getBoundingClientRect();
    const agentBlockRect = agentBlock.getBoundingClientRect();
    
    // Check if mobile view
    const isMobile = window.innerWidth <= 567;
    
    // Calculate position relative to the agent block
    let timestampLeft, timestampTop;
    
    if (isMobile) {
      // Mobile positioning - center below avatar
      timestampLeft = avatarRect.left - agentBlockRect.left + (avatarRect.width / 2) - 15; // Center horizontally
      timestampTop = avatarRect.bottom - agentBlockRect.top + 5; // 5px below avatar
    } else {
      // Desktop positioning - center below avatar
      timestampLeft = avatarRect.left - agentBlockRect.left + (avatarRect.width / 2) - 20; // Center horizontally
      timestampTop = avatarRect.bottom - agentBlockRect.top + 8; // 8px below avatar
    }
    
    timestampSpan.style.left = `${timestampLeft}px`;
    timestampSpan.style.top = `${timestampTop}px`;
    timestampSpan.style.right = 'auto';
    timestampSpan.style.bottom = 'auto';
    timestampSpan.style.textAlign = 'center'; // Center the text
  }
}



function createUserMessage(text) {
  const userBlock = document.createElement("div");
  userBlock.className = "user-container";

  const userMessage = document.createElement("div");
  userMessage.className = "message-content";
  userMessage.innerHTML = `<span>${text}</span>`;

  userBlock.appendChild(userMessage);
  
  // Add timestamp outside the message content
  const timestamp = getCurrentTime();
  const timestampSpan = document.createElement('span');
  timestampSpan.className = 'message-timestamp';
  timestampSpan.textContent = timestamp;
  timestampSpan.style.opacity = '0'; // Start hidden
  userBlock.appendChild(timestampSpan);
  
  // Position timestamp at the bottom right of the user message (same as agent)
  setTimeout(() => {
    const userMessageRect = userMessage.getBoundingClientRect();
    const userBlockRect = userBlock.getBoundingClientRect();
    
    // Check if mobile view
    const isMobile = window.innerWidth <= 567;
    
    let timestampLeft, timestampTop;
    
    if (isMobile) {
      // Mobile positioning - same behavior as agent but on the left
      timestampLeft = userMessageRect.left - userBlockRect.left - 30; // 15px to the left of the message
      timestampTop = userMessageRect.bottom - userBlockRect.top - 12; // Align bottom with message
    } else {
      // Desktop positioning - same behavior as agent but on the left
      timestampLeft = userMessageRect.left - userBlockRect.left - 35; // 20px to the left of the message
      timestampTop = userMessageRect.bottom - userBlockRect.top - 15; // Align bottom with message
    }
    
    timestampSpan.style.left = `${timestampLeft}px`;
    timestampSpan.style.top = `${timestampTop}px`;
    timestampSpan.style.right = 'auto';
    timestampSpan.style.bottom = 'auto';
    timestampSpan.style.opacity = '1'; // Show timestamp
    timestampSpan.style.transition = 'opacity 0.3s ease'; // Smooth fade in
  }, 300); // Longer delay to ensure content is fully rendered
  
  return userBlock;
}

function createChatMessage(text, isTyping = false) {
  const chatMessage = document.createElement("div");

  if (isTyping) {
    chatMessage.className = "typing-container";
    chatMessage.innerHTML = typingEffect();
  } else {
    chatMessage.className = "message-content";
    chatMessage.innerHTML = `<p>${text}</p>`;
  }

  return chatMessage;
}

function createSelectionButtons(selections) {
  const selectionContainer = document.createElement("div");
  const hasSpecialBtn = selections.some(option => option.stBtn === "Yes");

  selectionContainer.className = hasSpecialBtn
    ? "agent-chat-options"
    : "agent-chat-options";

  selections.forEach((option, index) => {
    let element;

    if (option.href) {
      element = document.createElement("a");
      element.href = option.href;
      element.target = "_blank";
      element.rel = "noopener noreferrer";
      element.textContent = option.title;
      
      // Determine if this is a secondary button (Can't Talk Now)
      if (option.title.includes("Can't Talk Now")) {
        element.className = "link-style secondary-btn";
      } else {
        element.className = "link-style";
      }
    } else {
      element = document.createElement("button");
      element.textContent = option.title;

      if (option.stBtn) {
        element.classList.add("special-start-btn");
        element.onclick = (e) => {
          // Disable all buttons in this container to prevent multiple clicks
          const buttons = selectionContainer.querySelectorAll('button, a');
          buttons.forEach(btn => {
            btn.style.pointerEvents = 'none';
            btn.style.opacity = '0.6';
          });
          handleUserResponse(option, "st");
        };
      } else {
        // Determine if this is a secondary button (Can't Talk Now)
        if (option.title.includes("Can't Talk Now")) {
          element.classList.add("opt-btn", "secondary-btn");
        } else {
          element.classList.add("opt-btn");
        }
        element.onclick = (e) => {
          // Disable all buttons in this container to prevent multiple clicks
          const buttons = selectionContainer.querySelectorAll('button, a');
          buttons.forEach(btn => {
            btn.style.pointerEvents = 'none';
            btn.style.opacity = '0.6';
          });
          handleUserResponse(option);
        };
      }
    }

    selectionContainer.appendChild(element);
  });

  return selectionContainer;
}

// ============================================================================
// MESSAGE DISPLAY FUNCTIONS
// ============================================================================

function addUserMessage(text) {
  const chatContainer = document.getElementById("chatContainer");
  const userBlock = createUserMessage(text);
  chatContainer.appendChild(userBlock);
  
  // Scroll if new content overflows
  setTimeout(() => {
    scrollToBottom();
  }, 100);
}

function addBotMessage(text) {
  const chatContainer = document.getElementById("chatContainer");
  const { agentBlock, chatBubbleContainer } = createAgentBlock();
  
  const chatMessage = createChatMessage(text);
  chatBubbleContainer.appendChild(chatMessage);
  
  chatContainer.appendChild(agentBlock);
  
  // Position avatar after content is fully rendered
  setTimeout(() => {
    positionAvatarAtLastMessage(agentBlock);
    scrollToBottom(); // Scroll if new content overflows
  }, 300); // Longer delay to ensure content is fully rendered
}

// ============================================================================
// FORM HANDLING
// ============================================================================

function showScheduleForm() {
  const chatContainer = document.getElementById("chatContainer");
  chatContainer.classList.add("pb-[80px]");

  // Create bot message
  const { agentBlock, chatBubbleContainer } = createAgentBlock();

  const chatMessage = createChatMessage("📝 Please complete the form below to schedule your call.");
  chatBubbleContainer.appendChild(chatMessage);
  
  chatContainer.appendChild(agentBlock);

  // Create form
  const formBlock = document.createElement("div");
  formBlock.className = "agent-container mt-2 subsequent";

  const formAvatarContainer = document.createElement("div");
  formAvatarContainer.className = "agent-img avatar-container";
  const formAvatar = document.createElement("img");
  formAvatar.src = "./assets/agent.jpg";
  formAvatar.alt = "Mia Avatar";
  formAvatar.className = "w-8 h-8 rounded-full";
  formAvatarContainer.appendChild(formAvatar);
  formBlock.appendChild(formAvatarContainer);

  const formContainer = document.createElement("div");
  formContainer.className = "agent-chat";
  formBlock.appendChild(formContainer);

  const formWrapper = document.createElement("div");
  formWrapper.className = "py-6 px-4 sm:px-6 rounded-lg shadow-md bg-white text-gray-800 w-full max-w-md";

  formWrapper.innerHTML = `
    <form id="scheduleForm" class="space-y-6">
      <div class="mb-4">
        <h3 class="text-lg font-semibold text-gray-800">Schedule Your Call</h3>
        <p class="text-sm text-gray-600">Fill out the form below and we'll contact you within 5 minutes</p>
      </div>

      <input type="hidden" name="f_totaldebt" value="${selectedDebtAmount || ''}" />
      <input type="hidden" name="f_affiliateid" value="Facebook" />

      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">Full Name</label>
        <div class="relative">
          <span class="absolute left-3 top-3.5 text-gray-400">👤</span>
          <input type="text" name="full_name" required placeholder="Enter your full name"
            class="pl-10 pr-4 py-2.5 w-full border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#005e54] bg-white" />
        </div>
      </div>

      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">Email</label>
        <div class="relative">
          <span class="absolute left-3 top-3.5 text-gray-400">📧</span>
          <input type="email" name="f_email" required placeholder="Enter your email"
            class="pl-10 pr-4 py-2.5 w-full border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#005e54] bg-white" />
        </div>
      </div>

      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">Phone Number</label>
        <div class="relative">
          <span class="absolute left-3 top-3.5 text-gray-400">📱</span>
          <input type="tel" name="f_phone" required placeholder="Enter your phone number"
            class="pl-10 pr-4 py-2.5 w-full border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#005e54] bg-white" />
        </div>
      </div>

      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">State</label>
        <div class="relative">
          <select name="f_whereyoulive" required
            class="appearance-none w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#005e54] bg-white">
            <option value="">Select your state</option>
            ${[
      "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA",
      "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN",
      "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY"
    ].map(state => `<option value="${state}">${state}</option>`).join("")}
          </select>
          <div class="absolute right-3 top-3.5 text-gray-400 pointer-events-none">▼</div>
        </div>
      </div>

      <div>
        <button type="submit"
          class="w-full flex justify-center items-center gap-2 bg-[#005e54] hover:bg-[#004a42] text-white py-3 px-6 rounded-lg text-base font-semibold shadow-md transition-transform transform hover:scale-[1.02] active:scale-[0.98]">
          📞 <span>Schedule My Call</span>
        </button>
      </div>

      <div class="text-xs text-gray-500 mt-6 border-t pt-4 flex justify-center gap-6">
        <div class="flex items-center gap-1.5"><span>🔒</span>Secure</div>
        <div class="flex items-center gap-1.5"><span>⚡</span>Fast</div>
        <div class="flex items-center gap-1.5"><span>✅</span>No Obligation</div>
      </div>
    </form>
  `;

  formContainer.appendChild(formWrapper);
  
  // Add timestamp to the form block
  const formTimestamp = getCurrentTime();
  const formTimestampSpan = document.createElement('span');
  formTimestampSpan.className = 'message-timestamp';
  formTimestampSpan.textContent = formTimestamp;
  formTimestampSpan.style.opacity = '0'; // Start hidden
  formBlock.appendChild(formTimestampSpan);
  
  chatContainer.appendChild(formBlock);
  
  // Position avatar and show timestamp after content is fully rendered
  setTimeout(() => {
    positionAvatarAtLastMessage(formBlock);
    positionTimestampAtLastMessage(formBlock);
    formTimestampSpan.style.opacity = '1'; // Show timestamp
    formTimestampSpan.style.transition = 'opacity 0.3s ease'; // Smooth fade in
    scrollToBottom(); // Scroll if new content overflows
  }, 300); // Longer delay to ensure content is fully rendered

  const form = formWrapper.querySelector("#scheduleForm");
  form.addEventListener("submit", handleFormSubmit);
}

function handleFormSubmit(e) {
  e.preventDefault();

  const form = e.target;
  const submitBtn = form.querySelector('button[type="submit"]');
  const originalText = submitBtn.innerHTML;
  submitBtn.innerHTML = '<span class="text-lg">⏳</span> <span>Scheduling...</span>';
  submitBtn.disabled = true;
  submitBtn.classList.add('opacity-70', 'cursor-not-allowed');

  const fullName = form.full_name.value.trim();
  const [firstName, ...lastParts] = fullName.split(" ");
  const lastName = lastParts.join(" ") || "_";

  const params = new URLSearchParams();
  params.append("f_fname", firstName);
  params.append("f_lname", lastName);
  params.append("f_email", form.f_email.value);
  params.append("f_phone", form.f_phone.value);
  params.append("f_whereyoulive", form.f_whereyoulive.value);
  params.append("f_totaldebt", form.f_totaldebt.value);
  params.append("f_affiliateid", "Facebook");
  params.append("a_", "single-mom-debt-relief");
  params.append("b_fb", "1");

  const formBlock = form.closest('.agent-container');

  setTimeout(() => {
    formBlock.style.transform = "translateX(-100%)";
    formBlock.style.opacity = "0";
    formBlock.style.transition = "all 0.5s ease";

    setTimeout(() => {
      formBlock.style.display = "none";
      addBotMessage("✅ Perfect! Your information has been submitted. A Senior Counselor will contact you within the next 5 minutes.");
    }, 500);
  }, 1000);

  fetch("https://signup.curadebt.com/post/", {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: params.toString(),
  })
    .then((res) => {
      setTimeout(() => {
        formBlock.remove();
      }, 5000);
    })
    .catch((err) => {
      console.warn("Network error, assuming success.");
      setTimeout(() => {
        formBlock.remove();
      }, 5000);
    });
}

// ============================================================================
// USER RESPONSE HANDLING
// ============================================================================

function handleUserResponse(option, type) {
  const userMessage = type === "st" ? option.stBtn : option.title;
  addUserMessage(userMessage);

  // ✅ Capture debt value from first question
  if (currentSectionIndex === 0) {
    selectedDebtAmount = option.title.includes("Yes") ? 15000 : 10000;
  }

  // Hide the buttons after selection
  const chatContainer = document.getElementById("chatContainer");
  const selectionBlocks = chatContainer.querySelectorAll(".agent-chat-options");
  if (selectionBlocks.length > 0) {
    const lastSelectionBlock = selectionBlocks[selectionBlocks.length - 1];
    lastSelectionBlock.classList.add("hiding");
    
    // Remove the block after animation
    setTimeout(() => {
      lastSelectionBlock.remove();
    }, 300);
  }

  // ✅ Replace form with redirect
if (option.title.includes("Busy? Request A Call Back")) {
    fbq('track', 'Schedule'); // 🔥 Fire Facebook Lead event
  const queryString = window.location.search; // includes the '?'
  const targetURL = `https://www.curadebt.com/debtpps/${queryString}`;
  setTimeout(() => {
    window.location.href = targetURL;
  }, 800);
  return;
}

// ✅ If user clicks "Call Now", trigger dial immediately
if (option.stBtn === "Call Now") {
      // 🔥 Fire Facebook Pixel Contact event
  fbq('track', 'Contact');
    // Trigger Ringba call link
  const link = document.getElementById('ringbaCallLink');
  if (link) {
    link.click(); // Trigger the <a href="tel:..."> link that Ringba replaced
  } else {
    console.warn("Ringba call link not found");
  }
  return;
}


  if (option.nextSectionIndex !== undefined) {
    currentSectionIndex = option.nextSectionIndex;
    setTimeout(() => handleSection(currentSectionIndex), 800);
  }
}

// ============================================================================
// MAIN MESSAGE DISPLAY FUNCTION
// ============================================================================

async function displayMessage(section) {
  const chatContainer = document.getElementById("chatContainer");
  let agentBlock = null;
  let chatBubbleContainer = null;

  for (let i = 0; i < section.messages.length; i++) {
    const message = section.messages[i];
    const isSelectionOnly = message.selections && !message.text;

    if (!isSelectionOnly) {
      if (!agentBlock) {
        // Create a new agent block for this message
        const blockData = createAgentBlock();
        agentBlock = blockData.agentBlock;
        chatBubbleContainer = blockData.chatBubbleContainer;
        chatContainer.appendChild(agentBlock);
      }

      // Position avatar at the last message (no animation)
      const existingMessages = agentBlock.querySelectorAll('.message-content');
      if (existingMessages.length > 0) {
        positionAvatarAtLastMessage(agentBlock);
      }

      // Create typing animation at the bottom
      const typingMessage = createChatMessage(message.text, true);
      chatBubbleContainer.appendChild(typingMessage);

      await new Promise((resolve) => setTimeout(resolve, message.delay));

      // Remove typing animation and create actual message
      typingMessage.remove();
      const chatMessage = createChatMessage(message.text, false);
      
      chatBubbleContainer.appendChild(chatMessage);
      
      // Position avatar after content is fully rendered
      setTimeout(() => {
        positionAvatarAtLastMessage(agentBlock);
      }, 300); // Longer delay to ensure content is fully rendered
    }

    if (message.selections) {
      const selectionBlock = createSelectionButtons(message.selections);
      chatBubbleContainer.appendChild(selectionBlock);
      
      // Add timestamp only when buttons appear
      const timestamp = getCurrentTime();
      const timestampSpan = document.createElement('span');
      timestampSpan.className = 'message-timestamp';
      timestampSpan.textContent = timestamp;
      timestampSpan.style.opacity = '0'; // Start hidden
      
      // Add timestamp to the agent container (outside message content)
      agentBlock.appendChild(timestampSpan);
      
      // Position avatar and show timestamp after content is fully rendered
      setTimeout(() => {
        positionAvatarAtLastMessage(agentBlock);
        positionTimestampAtLastMessage(agentBlock);
        timestampSpan.style.opacity = '1'; // Show timestamp
        timestampSpan.style.transition = 'opacity 0.3s ease'; // Smooth fade in
        scrollToBottom(); // Scroll if new content overflows
      }, 300); // Longer delay to ensure content is fully rendered
    }
  }
}

// ============================================================================
// SECTION HANDLING
// ============================================================================

async function handleSection(sectionIndex) {
  const section = sections[sectionIndex];
  await displayMessage(section);
}

// ============================================================================
// INITIALIZATION
// ============================================================================

// Start the chat when the page loads
document.addEventListener('DOMContentLoaded', function () {
  console.log('DOM loaded, starting chat...');
  handleSection(currentSectionIndex);
  
  // Handle window resize for timestamp repositioning only
  let resizeTimeout;
  window.addEventListener('resize', function() {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(() => {
      // Reposition timestamps after resize
      const agentBlocks = document.querySelectorAll('.agent-container');
      agentBlocks.forEach(block => {
        positionAvatarAtLastMessage(block);
        positionTimestampAtLastMessage(block);
      });
      
      // Reposition user timestamps
      const userBlocks = document.querySelectorAll('.user-container');
      userBlocks.forEach(block => {
        const timestampSpan = block.querySelector('.message-timestamp');
        const userMessage = block.querySelector('.message-content');
        if (timestampSpan && userMessage) {
          const userMessageRect = userMessage.getBoundingClientRect();
          const userBlockRect = block.getBoundingClientRect();
          const isMobile = window.innerWidth <= 567;
          
          let timestampLeft, timestampTop;
          
          if (isMobile) {
            timestampLeft = userMessageRect.left - userBlockRect.left - 30;
            timestampTop = userMessageRect.bottom - userBlockRect.top - 12;
          } else {
            timestampLeft = userMessageRect.left - userBlockRect.left - 35;
            timestampTop = userMessageRect.bottom - userBlockRect.top - 15;
          }
          
          timestampSpan.style.left = `${timestampLeft}px`;
          timestampSpan.style.top = `${timestampTop}px`;
          timestampSpan.style.right = 'auto';
          timestampSpan.style.bottom = 'auto';
        }
      });
    }, 250); // Debounce resize events
  });
});
