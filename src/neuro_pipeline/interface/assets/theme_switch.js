console.log('theme_switch.js loaded');

// Wait for DOM to be ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initSidebarToggle);
} else {
    initSidebarToggle();
}

function initSidebarToggle() {
    const toggleBtn = document.querySelector('.sidebar-toggle');
    const sidebar = document.querySelector('.sidebar');
    
    if (!toggleBtn || !sidebar) {
        console.log('Sidebar elements not found, will retry...');
        setTimeout(initSidebarToggle, 500);
        return;
    }
    
    // Prevent duplicate event listeners
    if (toggleBtn._sidebarBound) {
        return;
    }
    toggleBtn._sidebarBound = true;
    
    toggleBtn.addEventListener('click', function() {
        sidebar.classList.toggle('collapsed');
        console.log('Sidebar toggled:', sidebar.classList.contains('collapsed') ? 'collapsed' : 'expanded');
    });
    
    console.log('Sidebar toggle initialized');
}

// Watch for dynamic content changes (for Dash page navigation)
const observer = new MutationObserver(function(mutations) {
    const toggleBtn = document.querySelector('.sidebar-toggle');
    if (toggleBtn && !toggleBtn._sidebarBound) {
        initSidebarToggle();
    }
});

observer.observe(document.body, {
    childList: true,
    subtree: true
});