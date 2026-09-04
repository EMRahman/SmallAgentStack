const menuButton = document.querySelector(".menu-button");
const mobileNav = document.querySelector(".mobile-nav");

menuButton?.addEventListener("click", () => {
  const open = menuButton.getAttribute("aria-expanded") === "true";
  menuButton.setAttribute("aria-expanded", String(!open));
  mobileNav.hidden = open;
});

mobileNav?.querySelectorAll("a").forEach((link) => {
  link.addEventListener("click", () => {
    menuButton?.setAttribute("aria-expanded", "false");
    mobileNav.hidden = true;
  });
});

const toast = document.querySelector(".toast");
let toastTimer;

function showToast(message = "Copied to clipboard") {
  if (!toast) return;
  toast.textContent = message;
  toast.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("show"), 1800);
}

async function copyText(text, button) {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    const input = document.createElement("textarea");
    input.value = text;
    input.style.position = "fixed";
    input.style.opacity = "0";
    document.body.appendChild(input);
    input.select();
    document.execCommand("copy");
    input.remove();
  }

  const previous = button.textContent;
  button.classList.add("is-copied");
  button.textContent = "Copied";
  showToast();
  setTimeout(() => {
    button.classList.remove("is-copied");
    button.textContent = previous;
  }, 1600);
}

document.querySelectorAll("[data-copy], [data-copy-target]").forEach((button) => {
  button.addEventListener("click", () => {
    const targetId = button.dataset.copyTarget;
    const targetText = targetId ? document.getElementById(targetId)?.innerText : button.dataset.copy;
    if (targetText) copyText(targetText, button);
  });
});

const expandButton = document.querySelector(".expand-prompt");
const migrationPrompt = document.getElementById("migration-prompt");

expandButton?.addEventListener("click", () => {
  const expanded = expandButton.getAttribute("aria-expanded") === "true";
  expandButton.setAttribute("aria-expanded", String(!expanded));
  migrationPrompt?.classList.toggle("is-expanded", !expanded);
  expandButton.textContent = expanded ? "Expand prompt" : "Collapse prompt";
});

const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
if (!reducedMotion && "IntersectionObserver" in window) {
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("in-view");
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.12 }
  );
  document.querySelectorAll(".reveal").forEach((element, index) => {
    element.style.transitionDelay = `${Math.min(index * 90, 360)}ms`;
    observer.observe(element);
  });
} else {
  document.querySelectorAll(".reveal").forEach((element) => element.classList.add("in-view"));
}
