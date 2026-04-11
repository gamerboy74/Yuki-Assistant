document.addEventListener('DOMContentLoaded', () => {
    // ── Generate Cosmic Stars ───────────────────────────────────────────
    const cosmicField = document.querySelector('.cosmic-field');
    const starCount = 150;

    for (let i = 0; i < starCount; i++) {
        const star = document.createElement('div');
        star.className = 'star';
        
        const size = Math.random() < 0.8 ? 1 : 2.5;
        const top = Math.random() * 100;
        const left = Math.random() * 100;
        const duration = 3 + Math.random() * 5;
        const delay = Math.random() * 8;
        const minOp = 0.05 + Math.random() * 0.2;
        const maxOp = 0.4 + Math.random() * 0.4;

        star.style.width = `${size}px`;
        star.style.height = `${size}px`;
        star.style.top = `${top}%`;
        star.style.left = `${left}%`;
        star.style.setProperty('--min-op', minOp);
        star.style.setProperty('--max-op', maxOp);
        star.style.animation = `twinkle ${duration}s ease-in-out infinite ${-delay}s`;

        cosmicField.appendChild(star);
    }

    // ── Intersection Observer for Scroll Reveals ────────────────────────
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('animate-reveal');
                observer.unobserve(entry.target);
            }
        });
    }, observerOptions);

    document.querySelectorAll('.glass-card, .section-header').forEach(el => {
        el.style.opacity = '0'; // Initial state
        observer.observe(el);
    });

    // ── Hover Parallex for the Orb ──────────────────────────────────────
    const orbContainer = document.querySelector('.orb-container');
    const followers = document.querySelectorAll('.follower');

    if (orbContainer && followers.length > 0) {
        let targetX = 0;
        let targetY = 0;
        let currentX = 0;
        let currentY = 0;

        document.addEventListener('mousemove', (e) => {
            // Calculate distance from center (Move TOWARDS mouse)
            targetX = (e.pageX - window.innerWidth / 2) / 10;
            targetY = (e.pageY - window.innerHeight / 2) / 10;
        });

        function updateOrb() {
            // Smooth interpolation (lerp)
            currentX += (targetX - currentX) * 0.08;
            currentY += (targetY - currentY) * 0.08;

            followers.forEach(follower => {
                const speed = parseFloat(follower.getAttribute('data-speed')) || 1;
                const x = currentX * speed;
                const y = currentY * speed;
                follower.style.transform = `translate(${x}px, ${y}px)`;
            });

            requestAnimationFrame(updateOrb);
        }

        updateOrb();
    }

    // ── CTA Interaction ──────────────────────────────────────────────────
    const mainCta = document.querySelector('.btn-primary');
    if (mainCta) {
        mainCta.addEventListener('click', () => {
            mainCta.innerText = 'INITIALIZING...';
            mainCta.style.boxShadow = '0 0 50px #8ff5ff';
            setTimeout(() => {
                alert('Yuki Neural Link System: Standalone browser preview active. To use full system control, please launch via Electron.');
                mainCta.innerText = 'Neural Link Active';
            }, 1200);
        });
    }
});
