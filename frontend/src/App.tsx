import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
})

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <div className="min-h-screen bg-gray-50">
        <header className="bg-white shadow">
          <div className="max-w-7xl mx-auto px-4 py-6">
            <h1 className="text-3xl font-bold text-gray-900">JobPilot</h1>
            <p className="mt-1 text-sm text-gray-600">AI-powered job application assistant</p>
          </div>
        </header>
        <main className="max-w-7xl mx-auto px-4 py-6">
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-2xl font-semibold text-gray-800 mb-4">
              Frontend is ready! 🚀
            </h2>
            <p className="text-gray-600">
              The project structure is set up and ready for development.
            </p>
            <div className="mt-4 text-sm text-gray-500">
              <p>✅ React + Vite</p>
              <p>✅ TypeScript</p>
              <p>✅ Tailwind CSS</p>
              <p>✅ Axios + React Query</p>
              <p>✅ Zustand (ready to use)</p>
            </div>
          </div>
        </main>
      </div>
    </QueryClientProvider>
  )
}

export default App
