import re

file_path = r"c:\employee_tracker\templates\dashboard_new.html"

with open(file_path, "r", encoding="utf-8") as f:
    html = f.read()

# Fix Modal Backdrops & Containers
html = html.replace('bg-white px-6 pt-5 pb-4', 'bg-white dark:bg-slate-800 px-6 pt-5 pb-4')
html = html.replace('bg-white px-4 pb-4 pt-5', 'bg-white dark:bg-slate-800 px-4 pb-4 pt-5')
html = html.replace('bg-white px-4 py-3', 'bg-white dark:bg-slate-800 px-4 py-3')
html = html.replace('bg-gray-50 px-6 py-4', 'bg-gray-50 dark:bg-slate-900 px-6 py-4 px-6')
html = html.replace('bg-gray-50 max-h-96', 'bg-gray-50 dark:bg-slate-900 max-h-96')
html = html.replace('bg-white text-left shadow-2xl', 'bg-white dark:bg-slate-800 text-left shadow-2xl')

# Fix Inputs in modals
html = html.replace('border border-gray-300 rounded-md', 'border border-gray-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-gray-900 dark:text-white rounded-md')

# Fix Modal Text Colors
html = html.replace('text-gray-900 mb-1', 'text-gray-900 dark:text-white mb-1')
html = html.replace('text-gray-900 mb-2', 'text-gray-900 dark:text-white mb-2')
html = html.replace('text-gray-700 mb-1', 'text-gray-700 dark:text-gray-300 mb-1')
html = html.replace('text-gray-900"><i', 'text-gray-900 dark:text-white"><i')
html = html.replace('text-gray-900 flex', 'text-gray-900 dark:text-white flex')
html = html.replace('text-gray-600 mb-6', 'text-gray-600 dark:text-gray-400 mb-6')
html = html.replace('text-gray-600 mb-4', 'text-gray-600 dark:text-gray-400 mb-4')
html = html.replace('text-gray-900', 'text-gray-900 dark:text-white')
html = html.replace('text-gray-700', 'text-gray-700 dark:text-gray-300')
html = html.replace('text-gray-800', 'text-gray-800 dark:text-gray-100')
html = html.replace('text-gray-600', 'text-gray-600 dark:text-gray-400')

# De-duplicate dark text classes
html = html.replace('dark:text-white dark:text-white', 'dark:text-white')
html = html.replace('dark:text-gray-300 dark:text-gray-300', 'dark:text-gray-300')

# Add dark styling to hardcoded CSS components
css_fixes = """
        .dark .modal-content {
            background: #1e293b;
        }
        .dark .tour-tooltip {
            background: #1e293b;
        }
        .dark .tour-tooltip::before {
            background: #1e293b;
        }
        .dark .gate-card {
            background: #1e293b;
        }
"""
html = html.replace("</style>", css_fixes + "\n    </style>")

# Mobile Sidebar Fixes
sidebar_old = '''<aside
            class="w-64 bg-white dark:bg-slate-950 text-slate-900 dark:text-white flex flex-col flex-shrink-0 transition-all duration-300 border-r border-slate-200 dark:border-slate-800">'''

sidebar_new = '''<!-- Mobile Sidebar Overlay -->
        <div id="sidebar-overlay" onclick="toggleSidebar()" class="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-40 hidden md:hidden"></div>

        <aside id="sidebar"
            class="fixed inset-y-0 left-0 z-50 w-64 bg-white dark:bg-slate-950 text-slate-900 dark:text-white flex flex-col flex-shrink-0 transition-transform duration-300 border-r border-slate-200 dark:border-slate-800 transform -translate-x-full md:relative md:translate-x-0">'''

html = html.replace(sidebar_old, sidebar_new)

header_old = '''<h2 id="page-title" class="text-xl font-bold text-gray-800 dark:text-gray-100 dark:text-white">Dashboard</h2>'''
header_new = '''<div class="flex items-center gap-4">
                    <button class="md:hidden text-slate-500 hover:text-gray-800 dark:text-gray-100 dark:text-slate-400 dark:hover:text-white" onclick="toggleSidebar()">
                        <i class="fa-solid fa-bars text-xl"></i>
                    </button>
                    <h2 id="page-title" class="text-xl font-bold text-gray-800 dark:text-gray-100 dark:text-white">Dashboard</h2>
                </div>'''

# We also should consider if `text-gray-800 dark:text-white` was replaced by `text-gray-800 dark:text-gray-100 dark:text-white`.
# Let's just do a regex replace for the header title to be safe.
header_rx = re.compile(r'<h2 id="page-title"[^>]*>Dashboard</h2>')
html = header_rx.sub(r'''<div class="flex items-center gap-4">
                    <button class="md:hidden text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-white" onclick="toggleSidebar()">
                        <i class="fa-solid fa-bars text-xl"></i>
                    </button>
                    <h2 id="page-title" class="text-xl font-bold text-slate-800 dark:text-white">Dashboard</h2>
                </div>''', html)

# Function to toggle sidebar
js_toggle = """
// UI Toggle JS
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebar-overlay');
    sidebar.classList.toggle('-translate-x-full');
    overlay.classList.toggle('hidden');
}

// Ensure clickingnav items closes sidebar on mobile
document.querySelectorAll('.sidebar-link').forEach(link => {
    link.addEventListener('click', () => {
        if (window.innerWidth < 768) {
            toggleSidebar();
        }
    });
});
"""
html = html.replace("</script>\n</body>", js_toggle + "\n</script>\n</body>")

with open(file_path, "w", encoding="utf-8") as f:
    f.write(html)

print("UI fixes applied!")
