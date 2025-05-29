document.addEventListener('DOMContentLoaded', function () {
  const teamCards = document.querySelectorAll('.team-card');

  function initializeParallaxEffect() {
    /**
     * Initializes the parallax effect for team cards.
     */
    teamCards.forEach(card => {
      card.addEventListener('mousemove', function (e) {
        /**
         * Handles the mousemove event for parallax effect.
         *
         * @param {MouseEvent} e - The mouse event.
         */
        const rect = this.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        const centerX = rect.width / 2;
        const centerY = rect.height / 2;

        const angleX = (y - centerY) / 20;
        const angleY = (centerX - x) / 20;

        this.style.transform = `perspective(1000px) rotateX(${angleX}deg) rotateY(${angleY}deg)`;

        const content = this.querySelector('.relative.z-10');
        if (content) {
          content.style.transform = `translateZ(20px)`;
        }

        const glowEffect = this.querySelector('.absolute.inset-0');
        if (glowEffect) {
          const percentX = (x / rect.width) * 100;
          const percentY = (y / rect.height) * 100;
          glowEffect.style.background = `radial-gradient(circle at ${percentX}% ${percentY}%, rgba(74, 222, 128, 0.15), transparent 50%)`;
        }
      });

      card.addEventListener('mouseleave', function () {
        /**
         * Handles the mouseleave event to reset the parallax effect.
         */
        this.style.transform = 'perspective(1000px) rotateX(0) rotateY(0)';
        this.style.transition = 'transform 0.5s ease';

        const content = this.querySelector('.relative.z-10');
        if (content) {
          content.style.transform = '';
          content.style.transition = 'transform 0.5s ease';
        }

        const glowEffect = this.querySelector('.absolute.inset-0');
        if (glowEffect) {
          glowEffect.style.background = '';
        }
      });
    });
  }

  function initializeValueIcons() {
    /**
     * Initializes the pulse animation for value icons on hover.
     */
    const valueIcons = document.querySelectorAll('.w-16.h-16.mx-auto');

    valueIcons.forEach(icon => {
      icon.addEventListener('mouseenter', function () {
        this.classList.add('animate-pulse');
      });

      icon.addEventListener('mouseleave', function () {
        this.classList.remove('animate-pulse');
      });
    });
  }

  function trackTeamPageAnalytics() {
    /**
     * Tracks team page analytics using gtag if available.
     */
    if (typeof gtag === 'function') {
      gtag('event', 'page_view', {
        page_title: 'Team Page',
        page_location: window.location.href,
        page_path: '/team'
      });
    }
  }

  initializeParallaxEffect();
  initializeValueIcons();
  trackTeamPageAnalytics();
});