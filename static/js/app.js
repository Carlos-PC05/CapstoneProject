document.addEventListener('DOMContentLoaded', function() {
    // Lógica de barra de progreso para scroll horizontal en móvil
    const categoryList = document.getElementById('categoryList');
    const progressBar = document.getElementById('progressBar');
    const track = document.querySelector('.scroll-progress-track');
    const returnButton = document.querySelector('.return-button');
    const favButtons = document.querySelectorAll('.favorite-btn');

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

    // Profile Photo Upload Logic
    const profilePhotoInput = document.getElementById('photo-input');
    if (profilePhotoInput) {
        profilePhotoInput.addEventListener('change', function() {
            if (this.files && this.files[0]) {
                document.getElementById('photo-form').submit();
            }
        });
    }

    // Return Button Logic
    if (returnButton) {
        returnButton.addEventListener('click', () => {
            const url = returnButton.dataset.url;
            if (url) {
                window.location.href = url;
            }
        });
    }

    // Upload Photos Button Logic
    const selectPhotosBtn = document.querySelector('.btn-select-photos');
    const itemPhotoInput = document.getElementById('photos');
    const uploadPlaceholder = document.querySelector('.photo-upload-section .upload-placeholder');
    const photoCount = document.getElementById('photo-count');
    const photoUploadSection = document.querySelector('.photo-upload-section');
    const maxPhotos = 6;
    let selectedItemFiles = [];
    let previewShell = null;
    let previewContainer = null;

    if (selectPhotosBtn && itemPhotoInput) {
        const fileSignature = (file) => `${file.name}-${file.size}-${file.lastModified}-${file.type}`;

        const addFilesToSelection = (incomingFiles) => {
            incomingFiles.forEach((file) => {
                if (!file.type.startsWith('image/')) return;
                if (selectedItemFiles.length >= maxPhotos) return;

                const alreadyExists = selectedItemFiles.some(
                    (selectedFile) => fileSignature(selectedFile) === fileSignature(file)
                );

                if (!alreadyExists) {
                    selectedItemFiles.push(file);
                }
            });
        };

        const syncInputFiles = () => {
            const dt = new DataTransfer();
            selectedItemFiles.forEach(file => dt.items.add(file));
            itemPhotoInput.files = dt.files;
        };

        const renderImagePreview = () => {
            const hasPhotos = selectedItemFiles.length > 0;

            if (hasPhotos && !previewShell && uploadPlaceholder) {
                previewShell = document.createElement('div');
                previewShell.id = 'preview-shell';
                previewShell.className = 'preview-shell';
                previewShell.setAttribute('aria-live', 'polite');

                previewContainer = document.createElement('div');
                previewContainer.id = 'image-preview-container';
                previewContainer.className = 'image-preview-container';

                previewShell.appendChild(previewContainer);
                uploadPlaceholder.appendChild(previewShell);
            }

            if (!hasPhotos && previewShell) {
                previewShell.remove();
                previewShell = null;
                previewContainer = null;
            }

            if (previewContainer) {
                previewContainer.innerHTML = '';
            }

            if (photoUploadSection) {
                photoUploadSection.classList.toggle('has-photos', hasPhotos);
            }

            if (previewShell) {
                previewShell.classList.toggle('is-visible', hasPhotos);
            }

            if (photoCount) {
                photoCount.textContent = hasPhotos ? `${selectedItemFiles.length}/${maxPhotos} selected` : '';
            }

            selectedItemFiles.forEach((file, index) => {
                if (!previewContainer) return;
                if (!file.type.startsWith('image/')) return;

                const previewItem = document.createElement('div');
                previewItem.classList.add('preview-item');

                const img = document.createElement('img');
                img.classList.add('preview-img');

                const removeBtn = document.createElement('button');
                removeBtn.type = 'button';
                removeBtn.classList.add('preview-remove-btn');
                removeBtn.setAttribute('aria-label', 'Remove image');
                removeBtn.setAttribute('title', 'Remove image');
                removeBtn.innerHTML = `
                    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                        <path d="M9 3h6l1 2h4v2H4V5h4l1-2zm1 6h2v8h-2V9zm4 0h2v8h-2V9zM7 9h2v8H7V9zm1 12h8a2 2 0 0 0 2-2V9H6v10a2 2 0 0 0 2 2z"/>
                    </svg>
                `;
                removeBtn.addEventListener('click', function() {
                    selectedItemFiles.splice(index, 1);
                    syncInputFiles();
                    renderImagePreview();
                });

                const reader = new FileReader();
                reader.onload = function(e) {
                    img.src = e.target.result;
                };
                reader.readAsDataURL(file);

                previewItem.appendChild(removeBtn);
                previewItem.appendChild(img);
                previewContainer.appendChild(previewItem);
            });

            // Keep the newest images in view when list overflows horizontally.
            if (previewContainer && hasPhotos) {
                previewContainer.scrollLeft = previewContainer.scrollWidth;
            }
        };

        selectPhotosBtn.addEventListener('click', function() {
            itemPhotoInput.click();
        });

        // Show preview when files are selected from the file picker.
        // Important: we APPEND files to the current selection instead of replacing it.
        // This guarantees that existing previews stay in place unless the user removes
        // a file with the trash button.
        itemPhotoInput.addEventListener('change', function() {
            const newFiles = Array.from(this.files || []);
            addFilesToSelection(newFiles);
            syncInputFiles();
            renderImagePreview();
        });

        /*
         * -------------------------------------------------------------
         * Drag & Drop for item photos (educational version with comments)
         * -------------------------------------------------------------
         *
         * Goal:
         * - Let the user drag image files over the upload area and drop them.
         * - Keep previously selected images (append behavior).
         * - Never remove existing images automatically.
         * - Only remove images when clicking the trash button.
         *
         * How browser drag/drop works:
         * - By default, dropping a file on the page can make the browser try to
         *   open that file directly (navigating away from your app).
         * - To avoid that, we must call `event.preventDefault()` on dragover/drop.
         *
         * Visual feedback:
         * - While files are dragged over our zone, we add a CSS class (`is-dragover`)
         *   to highlight the area.
         */
        const dropZone = photoUploadSection;

        if (dropZone) {
            let dragDepth = 0;

            // Helper used by dragover/drop handlers to cancel default browser behavior.
            const preventBrowserFileOpen = (event) => {
                event.preventDefault();
                event.stopPropagation();
            };

            // When the pointer carrying files enters the drop zone, we highlight it.
            dropZone.addEventListener('dragenter', (event) => {
                preventBrowserFileOpen(event);
                dragDepth += 1;
                dropZone.classList.add('is-dragover');
            });

            // This event fires continuously while dragging inside the zone.
            // We keep preventing default so dropping is allowed.
            dropZone.addEventListener('dragover', (event) => {
                preventBrowserFileOpen(event);
                dropZone.classList.add('is-dragover');
            });

            // Fired when dragging leaves the drop zone; remove highlight.
            dropZone.addEventListener('dragleave', (event) => {
                preventBrowserFileOpen(event);
                dragDepth -= 1;

                // dragenter/dragleave can fire many times due to child elements.
                // We only remove highlight when the pointer really leaves the zone.
                if (dragDepth <= 0) {
                    dragDepth = 0;
                    dropZone.classList.remove('is-dragover');
                }
            });

            // Main drop handler:
            // 1) cancel browser default
            // 2) remove visual highlight
            // 3) read dropped files
            // 4) append valid files to our selection
            // 5) sync hidden input + re-render previews
            dropZone.addEventListener('drop', (event) => {
                preventBrowserFileOpen(event);
                dragDepth = 0;
                dropZone.classList.remove('is-dragover');

                const droppedFiles = Array.from(event.dataTransfer?.files || []);
                addFilesToSelection(droppedFiles);
                syncInputFiles();
                renderImagePreview();
            });

            // Extra safety:
            // If a user drops files outside the zone, prevent the browser from
            // navigating away. We only do this on pages where the upload block exists.
            document.addEventListener('dragover', preventBrowserFileOpen);
            document.addEventListener('drop', preventBrowserFileOpen);
        }

        renderImagePreview();
    }
    
    if (favButtons.length > 0) {
        const favoritesPath = '/user/favItems';
        const toastContainer = document.getElementById('toast-container');

        const showToast = (message, type = 'success') => {
            if (!toastContainer) return;

            const toast = document.createElement('div');
            toast.className = `toast toast--${type}`;
            toast.setAttribute('role', 'status');

            const icon = type === 'success' ? '✓' : '!';
            toast.innerHTML = `
                <div class="toast__body">
                    <span class="toast__icon" aria-hidden="true">${icon}</span>
                    <span>${message}</span>
                </div>
                <button type="button" class="toast__close" aria-label="Dismiss alert">×</button>
            `;

            const removeToast = () => {
                if (!toast.parentElement) return;
                toast.classList.add('is-hiding');
                setTimeout(() => {
                    toast.remove();
                }, 180);
            };

            const closeBtn = toast.querySelector('.toast__close');
            if (closeBtn) {
                closeBtn.addEventListener('click', removeToast);
            }

            toastContainer.appendChild(toast);
            setTimeout(removeToast, 2600);
        };

        const applyFavoriteState = (button, isFavorite) => {
            button.classList.toggle('active', isFavorite);
            button.dataset.isFavorite = isFavorite ? 'true' : 'false';

            const heartIcon = button.querySelector('img');
            if (heartIcon) {
                heartIcon.src = isFavorite ? '/static/img/assets/RedHeart.svg' : '/static/img/assets/Heart.svg';
            }

            if (button.dataset.favoriteText === 'true') {
                button.textContent = isFavorite ? 'Remove from favorites' : 'Add to favorites';
            }
        };

        const maybeRenderEmptyFavoritesMessage = () => {
            if (window.location.pathname !== favoritesPath) return;
            if (document.querySelector('.contenedor-item')) return;
            if (document.querySelector('[data-empty-favorites]')) return;

            const message = document.createElement('p');
            message.textContent = 'You do not have favorite items yet.';
            message.setAttribute('data-empty-favorites', 'true');
            message.classList.add('favorites-empty-state');

            const contentRoot = document.querySelector('.favorites-page');
            if (contentRoot) {
                contentRoot.appendChild(message);
            }
        };

        favButtons.forEach((button) => {
            button.addEventListener('click', async function() {
                const itemId = this.dataset.itemId;
                if (!itemId || this.disabled) return;

                this.disabled = true;

                try {
                    const response = await fetch(`/item/${itemId}/favorite`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        }
                    });

                    if (!response.ok) {
                        throw new Error(`Favorite toggle failed (${response.status})`);
                    }

                    const data = await response.json();
                    if (!data.ok) {
                        throw new Error(data.error || 'Favorite toggle failed');
                    }

                    applyFavoriteState(this, data.is_favorite);
                    showToast(
                        data.is_favorite ? 'Added to favorites.' : 'Removed from favorites.',
                        'success'
                    );

                    if (window.location.pathname === favoritesPath && !data.is_favorite) {
                        const card = this.closest('.contenedor-item');
                        if (card) {
                            card.remove();
                            maybeRenderEmptyFavoritesMessage();
                        }
                    }
                } catch (error) {
                    // Keep current state if the server call fails.
                    console.error(error);
                    showToast('Could not update favorites. Try again.', 'error');
                } finally {
                    this.disabled = false;
                }
            });
        });
    }

    /* Lógica de filtros */
    const filterButtons = Array.from(document.querySelectorAll('.filter-button'));
    if (filterButtons.length) {
        const params = new URLSearchParams(window.location.search);
        const activeCategory = (params.get('category') || '').toLowerCase();

        const getCategoryFromHref = (href) => {
            if (!href) return '';
            try {
                const url = new URL(href, window.location.origin);
                return (url.searchParams.get('category') || '').toLowerCase();
            } catch (error) {
                return '';
            }
        };

        const setActive = (category) => {
            filterButtons.forEach((button) => {
                const buttonCategory = getCategoryFromHref(button.getAttribute('href'));
                button.classList.toggle('active', category && buttonCategory === category);
            });
        };

        setActive(activeCategory);

        filterButtons.forEach((button) => {
            button.addEventListener('click', () => {
                filterButtons.forEach((btn) => btn.classList.remove('active'));
                button.classList.add('active');
            });
        });
    }
    /* Fin de la lógica de filtros */

    /* Fin del archivo JS */
});
