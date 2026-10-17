import { Newspaper } from 'lucide-react'

function App() {
  return (
    <main className="min-h-screen flex flex-col items-center justify-center gap-4 bg-stone-50 text-stone-900">
      <Newspaper aria-hidden="true" className="size-12" />
      <h1 className="text-4xl font-bold tracking-tight">The Personal Morning Paper</h1>
      <p className="text-stone-600">Step 0 scaffold is running.</p>
    </main>
  )
}

export default App
