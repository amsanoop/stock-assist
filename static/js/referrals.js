function copyReferralLink() {
  /**
   * Copies the referral link to the clipboard and provides user feedback.
   */
  const referralLinkInput = document.getElementById('referralLink');
  referralLinkInput.select();
  document.execCommand('copy');

  const button = document.querySelector('button[onclick="copyReferralLink()"]');
  const originalText = button.textContent;
  button.textContent = 'Copied!';
  button.classList.add('bg-green-600');

  setTimeout(() => {
    button.textContent = originalText;
    button.classList.remove('bg-green-600');
  }, 2000);
}

function shareReferral(platform) {
  /**
   * Shares the referral link on the specified social media platform.
   *
   * @param {string} platform - The platform to share the link on (e.g., 'twitter', 'facebook').
   */
  const referralLink = document.getElementById('referralLink').value;
  const message = encodeURIComponent(`Join me on StockAssist for smarter stock analysis and insights! Use my referral link:`);

  let shareUrl = '';

  switch (platform) {
    case 'twitter':
      shareUrl = `https://twitter.com/intent/tweet?text=${message}&url=${encodeURIComponent(referralLink)}`;
      break;
    case 'facebook':
      shareUrl = `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(referralLink)}&quote=${message}`;
      break;
    case 'linkedin':
      shareUrl = `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(referralLink)}`;
      break;
    case 'email':
      shareUrl = `mailto:?subject=${encodeURIComponent('Join me on StockAssist')}&body=${message}%20${encodeURIComponent(referralLink)}`;
      break;
    case 'whatsapp':
      shareUrl = `https://api.whatsapp.com/send?text=${message}%20${encodeURIComponent(referralLink)}`;
      break;
  }

  if (shareUrl) {
    window.open(shareUrl, '_blank');
  }
}

document.addEventListener('DOMContentLoaded', function () {
  /**
   * Initializes referral page functionalities after the DOM is loaded.
   * This includes setting up confetti animations for reward claims
   * and initializing social sharing buttons.
   */
  const rewardButtons = document.querySelectorAll('.reward-button');
  const confettiCanvas = document.getElementById('confetti-canvas');

  if (rewardButtons.length && confettiCanvas) {
    rewardButtons.forEach(button => {
      button.addEventListener('click', function (e) {
        confettiCanvas.classList.remove('hidden');

        const level = parseInt(this.dataset.level);

        const colors = ['#4ade80', '#22D3EE', '#ffffff'];
        const duration = 3000 + (level * 500);

        confetti.create(confettiCanvas, {
          resize: true,
          useWorker: true
        })({
          particleCount: 100 + (level * 20),
          spread: 70 + (level * 10),
          origin: { y: 0.6 },
          colors: colors,
          disableForReducedMotion: true
        });

        setTimeout(() => {
          confettiCanvas.classList.add('hidden');
        }, duration);
      });
    });

    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.has('success')) {
      const level = parseInt(urlParams.get('level') || '1');

      confettiCanvas.classList.remove('hidden');

      const colors = ['#4ade80', '#22D3EE', '#ffffff'];
      const duration = 3000 + (level * 500);

      confetti.create(confettiCanvas, {
        resize: true,
        useWorker: true
      })({
        particleCount: 100 + (level * 20),
        spread: 70 + (level * 10),
        origin: { y: 0.6 },
        colors: colors,
        disableForReducedMotion: true
      });

      setTimeout(() => {
        confettiCanvas.classList.add('hidden');
      }, duration);
    }
  }

  const shareButtons = document.querySelectorAll('.share-button');
  if (shareButtons.length) {
    shareButtons.forEach(button => {
      button.addEventListener('click', function () {
        const platform = this.dataset.platform;
        shareReferral(platform);
      });
    });
  }
});