'use client'

import { useRef, useState } from 'react'
import Image from 'next/image'
import { ArrowRight, CheckCircle2, FileText, Upload, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { API_BASE_URL } from '@/lib/api'
import { saveSourcePdf } from '@/lib/pdf-storage'

export default function Page() {
  const inputRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [processing, setProcessing] = useState(false)
  const [error, setError] = useState('')

  function handleFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    const selectedFile = event.target.files?.[0]
    setError('')
    if (selectedFile && (selectedFile.type === 'application/pdf' || selectedFile.name.toLowerCase().endsWith('.pdf'))) {
      if (selectedFile.size > 20 * 1024 * 1024) {
        setFile(null)
        setError('El PDF supera el máximo permitido de 20 MB.')
        return
      }
      setFile(selectedFile)
    } else if (selectedFile) {
      setFile(null)
      setError('Seleccione un archivo en formato PDF.')
    }
  }

  async function handleProcess() {
    if (!file || processing) return
    setProcessing(true)
    setError('')

    try {
      const formData = new FormData()
      formData.append('archivo', file)
      const response = await fetch(`${API_BASE_URL}/documents/extract`, {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        const body = await response.json().catch(() => null)
        const detail = body?.detail
        const message = typeof detail === 'string'
          ? detail
          : typeof detail?.mensaje === 'string'
            ? detail.mensaje
            : 'No fue posible extraer la información del PDF.'
        throw new Error(message)
      }

      const result = await response.json()
      await saveSourcePdf(file)
      sessionStorage.setItem('identification-ficha', JSON.stringify(result.ficha))
      sessionStorage.setItem('identification-validacion', JSON.stringify(result.validacion))
      sessionStorage.setItem('identification-pdf-name', file.name)
      window.location.href = '/editar'
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'No se pudo conectar con el backend.')
      setProcessing(false)
    }
  }

  return (
    <main className="min-h-screen bg-[#222222] text-slate-100">
      <header className="border-b border-white/10">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-x-4 gap-y-3 px-6 py-5 lg:px-8">
          <div className="flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-md bg-[#00508C]" aria-hidden="true">
              <FileText className="size-5 text-white" />
            </div>
            <div>
              <p className="text-sm font-semibold tracking-wide text-white">Sistema de Identificación</p>
              <p className="text-xs text-slate-400">Plataforma institucional</p>
            </div>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <span className="text-sm font-bold tracking-wide text-[#547a90] sm:text-base">ARCHIVA GOB</span>
            <Image src="/assets/archiva_utpn.png" alt="Isotipo Archiva" width={443} height={443} className="size-12 object-contain sm:size-14" priority />

          </div>
        </div>
      </header>

      <div className="mx-auto flex min-h-[calc(100vh-81px)] max-w-6xl items-center justify-center px-6 py-12 lg:px-8">
        <section className="w-full max-w-2xl">
          <div className="mb-10 text-center">
            <p className="mb-4 text-xs font-semibold uppercase tracking-[0.2em] text-[#55a7d8]">Generación de ficha</p>
            <h1 className="text-3xl font-semibold tracking-tight text-white sm:text-4xl">Cargar documento PDF</h1>
            <p className="mx-auto mt-4 max-w-xl text-base leading-7 text-slate-400">
              Seleccione un documento oficial en formato PDF para iniciar la generación de su ficha de identificación.
            </p>
          </div>

          <div className="rounded-lg border border-white/10 bg-[#2b2b2b] p-6 shadow-2xl shadow-black/20 sm:p-8">
            <div className="mb-6 flex items-start gap-3 border-b border-white/10 pb-5">
              <div className="mt-0.5 rounded-md bg-[#00508C]/20 p-2 text-[#63b5e9]">
                <Upload className="size-5" aria-hidden="true" />
              </div>
              <div>
                <h2 className="font-medium text-white">Documento de origen</h2>
                <p className="mt-1 text-sm text-slate-400">El archivo debe ser PDF y no superar los 20 MB.</p>
              </div>
            </div>

            <input ref={inputRef} type="file" accept="application/pdf,.pdf" onChange={handleFileChange} className="sr-only" />
            {!file ? (
              <button
                type="button"
                onClick={() => inputRef.current?.click()}
                className="flex min-h-48 w-full flex-col items-center justify-center rounded-md border border-dashed border-slate-600 bg-[#252525] px-6 text-center transition-colors hover:border-[#55a7d8] hover:bg-[#262c30] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#55a7d8] focus-visible:ring-offset-2 focus-visible:ring-offset-[#2b2b2b]"
              >
                <span className="mb-4 flex size-12 items-center justify-center rounded-full bg-[#00508C]/20 text-[#63b5e9]">
                  <Upload className="size-5" aria-hidden="true" />
                </span>
                <span className="font-medium text-white">Seleccione un archivo PDF</span>
                <span className="mt-2 text-sm text-slate-400">Haga clic aquí para buscarlo en su dispositivo</span>
              </button>
            ) : (
              <div className="flex min-h-48 items-center justify-between rounded-md border border-[#3e8ab9]/50 bg-[#00508C]/10 px-5">
                <div className="flex min-w-0 items-center gap-4">
                  <div className="flex size-11 shrink-0 items-center justify-center rounded-md bg-[#00508C] text-white"><FileText className="size-5" /></div>
                  <div className="min-w-0">
                    <p className="truncate font-medium text-white">{file.name}</p>
                    <p className="mt-1 text-sm text-slate-400">{(file.size / 1024 / 1024).toFixed(2)} MB · PDF listo para procesar</p>
                  </div>
                </div>
                <button type="button" onClick={() => { setFile(null); if (inputRef.current) inputRef.current.value = '' }} className="ml-4 rounded-md p-2 text-slate-400 hover:bg-white/10 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#55b5ed]" aria-label="Quitar archivo">
                  <X className="size-5" />
                </button>
              </div>
            )}

            <div className="mt-6 flex items-center justify-between gap-4 border-t border-white/10 pt-6">
              <div>
                <p className="text-xs leading-5 text-slate-500">La información será utilizada únicamente para generar la ficha.</p>
                {error && <p role="alert" className="mt-2 max-w-sm text-sm text-red-300">{error}</p>}
              </div>
              <Button type="button" disabled={!file || processing} onClick={handleProcess} className="shrink-0 bg-[#00508C] text-white hover:bg-[#0068b5] disabled:bg-slate-700 disabled:text-slate-500">
                {processing ? 'Procesando…' : 'Procesar documento'} <ArrowRight data-icon="inline-end" />
              </Button>
            </div>
          </div>

          <p className="mt-6 flex items-center justify-center gap-2 text-xs text-slate-500"><CheckCircle2 className="size-4 text-[#55a7d8]" /> Conexión segura y protegida</p>
        </section>
      </div>
    </main>
  )
}
