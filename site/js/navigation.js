/**
 * Navigation Utility Module
 * Provides utilities for site navigation and URL handling
 */

const Navigation = (() => {
  /**
   * Navigate to a given path
   * @param {string} path - Relative path or absolute URL
   */
  function navigate(path) {
    if (path) {
      window.location.href = path;
    }
  }

  /**
   * Get current file name (without .html)
   */
  function getCurrentPage() {
    const pathname = window.location.pathname;
    const filename = pathname.split('/').pop() || 'index.html';
    return filename;
  }

  /**
   * Check if a given path exists (basic check via URL)
   * @param {string} path - Relative or absolute path
   */
  async function pathExists(path) {
    try {
      const response = await fetch(path, { method: 'HEAD' });
      return response.ok;
    } catch (e) {
      return false;
    }
  }

  /**
   * Get next/prev gallery from a list
   * @param {Array} galleryList - List of gallery objects with 'path' and 'thumbnail'
   * @param {string} currentPath - Current gallery path
   * @param {string} direction - 'next' or 'prev'
   */
  function getAdjacentGallery(galleryList, currentPath, direction) {
    const index = galleryList.findIndex(g => g.path === currentPath);
    if (index === -1) return null;

    if (direction === 'next') {
      return galleryList[index + 1] || null;
    } else if (direction === 'prev') {
      return galleryList[index - 1] || null;
    }
    return null;
  }

  /**
   * Render breadcrumb items into a container
   * @param {HTMLElement|null} container - Breadcrumb wrapper element
   * @param {Array<{label: string, href?: string, current?: boolean, className?: string, id?: string}>} items
   */
  function renderBreadcrumbs(container, items) {
    if (!container) {
      return;
    }

    const normalizedItems = Array.isArray(items)
      ? items.filter((item) => item && item.label)
      : [];

    container.innerHTML = '';

    normalizedItems.forEach((item, index) => {
      if (index > 0) {
        const separator = document.createElement('span');
        separator.textContent = '›';
        container.appendChild(separator);
      }

      const useLink = !!item.href && !item.current;
      const element = document.createElement(useLink ? 'a' : 'span');

      if (item.id) {
        element.id = item.id;
      }
      if (item.className) {
        element.className = item.className;
      }
      if (useLink) {
        element.href = item.href;
      } else {
        element.classList.add('breadcrumb-current');
      }

      element.textContent = item.label;
      container.appendChild(element);
    });
  }

  return {
    navigate,
    getCurrentPage,
    pathExists,
    getAdjacentGallery,
    renderBreadcrumbs
  };
})();

if (typeof window !== 'undefined') {
  window.Navigation = Navigation;
}
