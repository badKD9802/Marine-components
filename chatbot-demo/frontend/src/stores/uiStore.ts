import { create } from 'zustand'

interface UIState {
  sidebarOpen: boolean
  darkMode: boolean
  toggleSidebar: () => void
  setSidebarOpen: (open: boolean) => void
  toggleDarkMode: () => void
}

export const useUIStore = create<UIState>((set) => ({
  sidebarOpen: true,
  darkMode: false,
  toggleSidebar: () => set(state => ({ sidebarOpen: !state.sidebarOpen })),
  setSidebarOpen: (open: boolean) => set({ sidebarOpen: open }),
  toggleDarkMode: () =>
    set(state => {
      const next = !state.darkMode
      if (typeof document !== 'undefined') {
        document.documentElement.classList.toggle('dark', next)
      }
      return { darkMode: next }
    }),
}))
