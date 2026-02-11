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
});
