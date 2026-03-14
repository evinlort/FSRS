const navToggle = document.querySelector("[data-nav-toggle]");
const nav = document.querySelector("[data-nav]");
const reviewRoot = document.querySelector("[data-review-root]");
const catalogSearchInput = document.querySelector("[data-search-input]");

if (navToggle && nav) {
  navToggle.addEventListener("click", () => {
    const isOpen = nav.dataset.open === "true";
    nav.dataset.open = String(!isOpen);
    navToggle.setAttribute("aria-expanded", String(!isOpen));
  });
}

if (catalogSearchInput) {
  document.addEventListener("keydown", (event) => {
    const activeTag = document.activeElement?.tagName;
    if (
      event.key !== "/" ||
      activeTag === "INPUT" ||
      activeTag === "TEXTAREA" ||
      activeTag === "SELECT"
    ) {
      return;
    }
    event.preventDefault();
    catalogSearchInput.focus();
  });
}

if (reviewRoot) {
  const revealButton = reviewRoot.querySelector("[data-review-reveal-btn]");
  const answer = reviewRoot.querySelector("[data-review-answer]");
  const details = reviewRoot.querySelector("[data-review-details]");
  const gradePanel = reviewRoot.querySelector("[data-review-grade-panel]");
  const ratingButtons = [...reviewRoot.querySelectorAll("[data-rating-key]")];
  let isRevealed = false;

  const revealAnswer = () => {
    if (!revealButton || !answer || !details || !gradePanel || isRevealed) {
      return;
    }
    answer.hidden = false;
    details.hidden = false;
    gradePanel.hidden = false;
    revealButton.hidden = true;
    isRevealed = true;
  };

  if (revealButton) {
    revealButton.addEventListener("click", revealAnswer);
  }

  document.addEventListener("keydown", (event) => {
    const activeTag = document.activeElement?.tagName;
    if (activeTag === "INPUT" || activeTag === "TEXTAREA" || activeTag === "SELECT") {
      return;
    }
    if (event.key === " " && !isRevealed) {
      event.preventDefault();
      revealAnswer();
      return;
    }
    if (!isRevealed) {
      return;
    }
    const button = ratingButtons.find((item) => item.dataset.ratingKey === event.key);
    if (!button) {
      return;
    }
    event.preventDefault();
    button.click();
  });
}
