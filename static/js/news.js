function renderMarkdown(text) {
  if (!window.marked) {
    console.warn('Marked library not loaded, displaying raw text');
    return text;
  }
  return marked.parse(text);
}

function openReaderMode(newsId) {
  /**
   * Opens the reader mode modal and populates it with news content.
   * @param {string} newsId - The ID of the news item to display.
   */
  const modal = document.getElementById("readerModal");
  const backdrop = modal.querySelector(".modal-backdrop");
  const content = modal.querySelector(".modal-content");

  fetch(`/api/news/${newsId}`)
    .then((response) => {
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      return response.json();
    })
    .then((news) => {
      document.getElementById("modalTitle").textContent = news.title;
      document.getElementById("modalProvider").textContent = news.provider;
      document.getElementById("modalDate").textContent = new Date(
        news.published_at
      ).toLocaleString(undefined, {
        year: "numeric",
        month: "long",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });

      const contentHTML = `
          <div class="prose prose-invert max-w-none">
              <div class="text-lg mb-8 text-white/80">
                  ${renderMarkdown(news.content || news.summary)}
              </div>
              <div class="mt-8 flex justify-end">
                  <a href="${news.source_link}" target="_blank" class="source-link">
                      Read on ${news.source}
                      <svg class="inline-block w-4 h-4 ml-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"></path>
                      </svg>
                  </a>
              </div>
          </div>
      `;

      document.getElementById("modalContent").innerHTML = contentHTML;

      modal.classList.remove("hidden");
      modal.classList.add("flex");

      requestAnimationFrame(() => {
        backdrop.classList.add("show");
        content.classList.add("show");
      });
    })
    .catch((error) => {
      console.error("Error fetching news details:", error);
    });
}

function closeReaderMode() {
  /**
   * Closes the reader mode modal.
   */
  const modal = document.getElementById("readerModal");
  const backdrop = modal.querySelector(".modal-backdrop");
  const content = modal.querySelector(".modal-content");

  backdrop.classList.remove("show");
  content.classList.remove("show");

  setTimeout(() => {
    modal.classList.remove("flex");
    modal.classList.add("hidden");
  }, 300);
}

document.getElementById("readerModal").addEventListener("click", function (
  event
) {
  /**
   * Closes the reader mode when clicking on the modal backdrop.
   * @param {Event} event - The click event.
   */
  if (
    event.target === this ||
    event.target.classList.contains("modal-backdrop")
  ) {
    closeReaderMode();
  }
});

document.addEventListener("keydown", function (event) {
  /**
   * Closes the reader mode when the Escape key is pressed.
   * @param {KeyboardEvent} event - The keyboard event.
   */
  if (event.key === "Escape") {
    closeReaderMode();
  }
});