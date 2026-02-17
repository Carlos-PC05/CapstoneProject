document.addEventListener('DOMContentLoaded', function() {
    // Lógica de barra de progreso para scroll horizontal en móvil
    const categoryList = document.getElementById('categoryList');
    const progressBar = document.getElementById('progressBar');
    const track = document.querySelector('.scroll-progress-track');

    function updateProgress() {
        if (!categoryList) return;
        
        const scrollLeft = categoryList.scrollLeft;
        const scrollWidth = categoryList.scrollWidth - categoryList.clientWidth;
        
        // Si no hay scroll (contenido cabe completo), ancho 0 o 100% según prefieras.
        // Aquí ocultamos la barra si no es necesaria
        if (scrollWidth <= 0) {
            if (track) track.style.opacity = '0';
        } else {
            if (track) track.style.opacity = '1';
            const percent = (scrollLeft / scrollWidth) * 100;
            if (progressBar) progressBar.style.width = percent + '%';
        }
    }

    if (categoryList) {
        categoryList.addEventListener('scroll', updateProgress);
        window.addEventListener('resize', updateProgress);
        // Inicializar
        updateProgress();
    }

    // Carousel Logic
    const carouselContainer = document.querySelector('.carousel-container');
    if (carouselContainer) {
        const track = carouselContainer.querySelector('.carousel-track');
        const slides = Array.from(track.children);
        const nextButton = carouselContainer.querySelector('.next-btn');
        const prevButton = carouselContainer.querySelector('.prev-btn');
        const indicators = carouselContainer.querySelectorAll('.indicator');
        
        let currentIndex = 0;

        function updateCarousel() {
            track.style.transform = `translateX(-${currentIndex * 100}%)`;
            
            // Update indicators
            if (indicators.length > 0) {
                indicators.forEach((ind, index) => {
                    if (index === currentIndex) {
                        ind.classList.add('active');
                        ind.style.backgroundColor = 'white';
                    } else {
                        ind.classList.remove('active');
                        ind.style.backgroundColor = 'rgba(255, 255, 255, 0.5)';
                    }
                });
            }
        }

        if (nextButton) {
            nextButton.addEventListener('click', () => {
                currentIndex = (currentIndex + 1) % slides.length;
                updateCarousel();
            });
        }

        if (prevButton) {
            prevButton.addEventListener('click', () => {
                currentIndex = (currentIndex - 1 + slides.length) % slides.length;
                updateCarousel();
            });
        }

        if (indicators.length > 0) {
            indicators.forEach((ind, index) => {
                ind.addEventListener('click', () => {
                    currentIndex = index;
                    updateCarousel();
                });
            });
        }
        
        // Touch support (simple swipe)
        let touchStartX = 0;
        let touchEndX = 0;
        
        track.addEventListener('touchstart', e => {
            touchStartX = e.changedTouches[0].screenX;
        }, {passive: true});
        
        track.addEventListener('touchend', e => {
            touchEndX = e.changedTouches[0].screenX;
            handleSwipe();
        }, {passive: true});
        
        function handleSwipe() {
            if (touchStartX - touchEndX > 50) {
                // Swipe Left (Next)
                currentIndex = (currentIndex + 1) % slides.length;
                updateCarousel();
            }
            if (touchEndX - touchStartX > 50) {
                // Swipe Right (Prev)
                currentIndex = (currentIndex - 1 + slides.length) % slides.length;
                updateCarousel();
            }
        }
    }
});
