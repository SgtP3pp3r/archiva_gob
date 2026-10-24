'use client'

import { useEffect, useState } from 'react'
import { ArrowLeft, Download, FileText } from 'lucide-react'
import { Button } from '@/components/ui/button'

export default function DocumentoPage() {
  const [pdf, setPdf] = useState<string | null>(null)
  const [fileName, setFileName] = useState('documento.pdf')

  useEffect(() => {
    setPdf(sessionStorage.getItem('identification-pdf'))
    setFileName(sessionStorage.getItem('identification-pdf-name') || 'documento.pdf')
  }, [])

  return (
    <main className="min-h-screen bg-[#222222] text-slate-100">
      <header className="border-b border-white/10">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-5 lg:px-8">
          <div className="flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-md bg-[#00508C]"><FileText className="size-5 text-white" /></div>
            <div><p className="text-sm font-semibold text-white">Sistema de Identificación</p><p className="text-xs text-slate-400">Vista previa del documento</p></div>
          </div>
          <Button nativeButton={false} render={<a href={pdf || '/'} download={fileName} />} variant="outline" className="border-white/15 bg-transparent text-slate-200 hover:bg-white/10 hover:text-white">
            <Download data-icon="inline-start" /> Descargar
          </Button>
        </div>
      </header>
      <div className="mx-auto flex max-w-7xl flex-col gap-5 px-6 py-8 lg:px-8">
        <div className="flex items-center justify-between gap-4">
          <div><p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#55a7d8]">Documento cargado</p><h1 className="mt-2 truncate text-xl font-semibold text-white">{fileName}</h1></div>
          <Button nativeButton={false} render={<a href="/" />} variant="ghost" className="text-slate-300 hover:bg-white/10 hover:text-white"><ArrowLeft data-icon="inline-start" /> Volver</Button>
        </div>
        <div className="min-h-[70vh] overflow-hidden rounded-md border border-white/10 bg-[#353535]">
          {pdf ? <iframe title={`Vista previa de ${fileName}`} src={pdf} className="h-[75vh] w-full bg-white" /> : <div className="flex h-[70vh] flex-col items-center justify-center gap-3 text-center"><FileText className="size-10 text-slate-500" /><p className="text-slate-300">No se encontró un documento cargado.</p><a href="/" className="text-sm text-[#63b5e9] hover:underline">Cargar un documento</a></div>}
        </div>
      </div>
    </main>
  )
}
