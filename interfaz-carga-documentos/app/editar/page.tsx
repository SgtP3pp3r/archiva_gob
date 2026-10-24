'use client'

import { useEffect, useState, type DragEvent } from 'react'
import { ArrowLeft, Download, FilePlus2, FileText, Plus, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { API_BASE_URL, getApiError } from '@/lib/api'
import { loadSourcePdf } from '@/lib/pdf-storage'

type Familiar = { nombre: string; fecha_nacimiento: string | null }
type FamiliarListKey = 'hermanos' | 'hermanas' | 'hijos' | 'hijas'
type FamiliarDrag = { key: FamiliarListKey; index: number }
const familyDestination: Record<FamiliarListKey, FamiliarListKey> = {
  hermanos: 'hermanas',
  hermanas: 'hermanos',
  hijos: 'hijas',
  hijas: 'hijos',
}
const isFamiliarListKey = (key: string): key is FamiliarListKey =>
  key === 'hermanos' || key === 'hermanas' || key === 'hijos' || key === 'hijas'
type DatosPersonales = {
  nombre: string | null
  fecha_nacimiento: string | null
  lugar_nacimiento: string | null
  estado: string
  domicilios: string[]
  telefonos: string[]
  telefono_emergencia: string | null
  ocupacion: string | null
  estado_civil: string | null
  edad: number | null
  alias: string | null
}
type DatosFamiliares = {
  madre: string | null
  padre: string | null
  hermanos: Familiar[]
  hermanas: Familiar[]
  pareja: string | null
  hijas: Familiar[]
  hijos: Familiar[]
}
type Carpeta = {
  nuc: string | null
  fecha_inicio: string | null
  delito: string | null
  calidad: string | null
  hechos: string | null
  unidad: string | null
}
type Vehiculo = {
  alta: string | null
  marca: string | null
  linea: string | null
  modelo: string | null
  placa: string | null
  serie: string | null
}
type FuenteAbierta = { descripcion: string; fecha_consulta: string | null; link: string | null }
type Fotografia = { fuente: string | null; fecha: string | null; nombre: string | null; numero_causa: string | null }
type Ficha = {
  fecha: string
  nuc: string | null
  datos_personales: DatosPersonales
  datos_familiares: DatosFamiliares
  carpetas: Carpeta[]
  vehiculos: Vehiculo[]
  registro_publico: string[]
  fuentes_abiertas: FuenteAbierta[]
  fotografias: Fotografia[]
  nota_fotografia: string | null
  observaciones: string | null
  foto_base64: string | null
}
type Incidencia = { nivel: 'error' | 'advertencia'; campo: string; mensaje: string }
type Validacion = { valido: boolean; incidencias: Incidencia[] }

const emptyFamiliar = (): Familiar => ({ nombre: '', fecha_nacimiento: null })
const emptyCarpeta = (): Carpeta => ({ nuc: null, fecha_inicio: null, delito: null, calidad: null, hechos: null, unidad: null })
const emptyVehiculo = (): Vehiculo => ({ alta: null, marca: null, linea: null, modelo: null, placa: null, serie: null })
const emptyFuente = (): FuenteAbierta => ({ descripcion: '', fecha_consulta: null, link: null })
const emptyFotografia = (): Fotografia => ({ fuente: null, fecha: null, nombre: null, numero_causa: null })

function InputField({
  label,
  value,
  onChange,
  type = 'text',
  placeholder,
}: {
  label: string
  value: string | number | null
  onChange: (value: string) => void
  type?: 'text' | 'date' | 'number'
  placeholder?: string
}) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm text-slate-300">{label}</span>
      <input
        type={type}
        value={value ?? ''}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-md border border-white/10 bg-[#222] px-3 py-2.5 text-sm text-white outline-none transition focus:border-[#55a7d8] focus:ring-1 focus:ring-[#55a7d8]"
      />
    </label>
  )
}

function TextAreaField({
  label,
  value,
  onChange,
  rows = 3,
}: {
  label: string
  value: string | null
  onChange: (value: string) => void
  rows?: number
}) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm text-slate-300">{label}</span>
      <textarea
        rows={rows}
        value={value ?? ''}
        onChange={(event) => onChange(event.target.value)}
        className="w-full resize-y rounded-md border border-white/10 bg-[#222] px-3 py-2.5 text-sm leading-6 text-white outline-none transition focus:border-[#55a7d8] focus:ring-1 focus:ring-[#55a7d8]"
      />
    </label>
  )
}

function Panel({ title, children, action }: { title: string; children: React.ReactNode; action?: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-white/10 bg-[#2b2b2b] p-5 sm:p-6">
      <div className="mb-5 flex items-center justify-between gap-3 border-b border-white/10 pb-4">
        <h2 className="font-semibold text-white">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  )
}

function AddButton({ onClick, label }: { onClick: () => void; label: string }) {
  return (
    <button type="button" onClick={onClick} className="inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-sm text-[#75c3f1] transition hover:bg-white/5">
      <Plus className="size-4" /> {label}
    </button>
  )
}

function RemoveButton({ onClick, label }: { onClick: () => void; label: string }) {
  return (
    <button type="button" onClick={onClick} aria-label={label} className="rounded-md p-2 text-slate-400 transition hover:bg-red-500/10 hover:text-red-300">
      <Trash2 className="size-4" />
    </button>
  )
}

export default function EditarPage() {
  const [ficha, setFicha] = useState<Ficha | null>(null)
  const [draggedFamiliar, setDraggedFamiliar] = useState<FamiliarDrag | null>(null)
  const [validacion, setValidacion] = useState<Validacion | null>(null)
  const [fileName, setFileName] = useState('documento.pdf')
  const [pdfUrl, setPdfUrl] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState('')
  const [downloaded, setDownloaded] = useState(false)

  useEffect(() => {
    try {
      const savedFicha = sessionStorage.getItem('identification-ficha')
      if (!savedFicha) return
      const restoredFicha = JSON.parse(savedFicha) as Ficha
      restoredFicha.datos_personales.estado ||= 'Chihuahua'
      setFicha(restoredFicha)
      const savedValidation = sessionStorage.getItem('identification-validacion')
      if (savedValidation) setValidacion(JSON.parse(savedValidation) as Validacion)
      setFileName(sessionStorage.getItem('identification-pdf-name') || 'documento.pdf')
    } catch {
      setError('No se pudieron recuperar los datos extraídos. Vuelva a cargar el PDF.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    let active = true
    let objectUrl: string | null = null

    loadSourcePdf()
      .then((pdf) => {
        if (!active || !pdf) return
        objectUrl = URL.createObjectURL(pdf)
        setPdfUrl(objectUrl)
      })
      .catch((cause: unknown) => {
        if (active) setError(cause instanceof Error ? cause.message : 'No se pudo abrir el PDF original.')
      })

    return () => {
      active = false
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [])

  useEffect(() => {
    if (ficha) sessionStorage.setItem('identification-ficha', JSON.stringify(ficha))
  }, [ficha])

  function updatePersonal<K extends keyof DatosPersonales>(key: K, value: DatosPersonales[K]) {
    setFicha((current) => current ? { ...current, datos_personales: { ...current.datos_personales, [key]: value } } : current)
  }

  function updateFamily<K extends keyof DatosFamiliares>(key: K, value: DatosFamiliares[K]) {
    setFicha((current) => current ? { ...current, datos_familiares: { ...current.datos_familiares, [key]: value } } : current)
  }

  function updateFamiliar(key: FamiliarListKey, index: number, value: Partial<Familiar>) {
    if (!ficha) return
    const updated = ficha.datos_familiares[key].map((item, itemIndex) => itemIndex === index ? { ...item, ...value } : item)
    updateFamily(key, updated)
  }

  function moveFamiliar(source: FamiliarDrag, destination: FamiliarListKey) {
    if (familyDestination[source.key] !== destination) return
    setFicha((current) => {
      if (!current) return current
      const origen = [...current.datos_familiares[source.key]]
      const [persona] = origen.splice(source.index, 1)
      if (!persona) return current
      return {
        ...current,
        datos_familiares: {
          ...current.datos_familiares,
          [source.key]: origen,
          [destination]: [...current.datos_familiares[destination], persona],
        },
      }
    })
    setDraggedFamiliar(null)
  }

  function startDraggingFamiliar(event: DragEvent<HTMLDivElement>, key: FamiliarListKey, index: number) {
    event.dataTransfer.effectAllowed = 'move'
    event.dataTransfer.setData('text/plain', `${key}:${index}`)
    setDraggedFamiliar({ key, index })
  }

  function dropFamiliar(event: DragEvent<HTMLDivElement>, destination: FamiliarListKey) {
    event.preventDefault()
    const [key, indexText] = event.dataTransfer.getData('text/plain').split(':')
    const index = Number(indexText)
    if (isFamiliarListKey(key) && Number.isInteger(index)) {
      moveFamiliar({ key, index }, destination)
    }
    setDraggedFamiliar(null)
  }

  function updateCarpeta(index: number, value: Partial<Carpeta>) {
    setFicha((current) => current ? { ...current, carpetas: current.carpetas.map((item, i) => i === index ? { ...item, ...value } : item) } : current)
  }

  function updateVehiculo(index: number, value: Partial<Vehiculo>) {
    setFicha((current) => current ? { ...current, vehiculos: current.vehiculos.map((item, i) => i === index ? { ...item, ...value } : item) } : current)
  }

  function updateFuente(index: number, value: Partial<FuenteAbierta>) {
    setFicha((current) => current ? { ...current, fuentes_abiertas: current.fuentes_abiertas.map((item, i) => i === index ? { ...item, ...value } : item) } : current)
  }

  function updateFotografia(index: number, value: Partial<Fotografia>) {
    setFicha((current) => current ? { ...current, fotografias: current.fotografias.map((item, i) => i === index ? { ...item, ...value } : item) } : current)
  }

  function updateStringList(key: 'domicilios' | 'telefonos' | 'registro_publico', index: number, value: string) {
    if (!ficha) return
    if (key === 'registro_publico') {
      const items = [...ficha.registro_publico]
      items[index] = value
      setFicha({ ...ficha, registro_publico: items })
    } else {
      const items = [...ficha.datos_personales[key]]
      items[index] = value
      updatePersonal(key, items)
    }
  }

  async function handleGenerate() {
    if (!ficha || generating) return
    setGenerating(true)
    setError('')
    setDownloaded(false)
    try {
      const response = await fetch(`${API_BASE_URL}/documents/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(ficha),
      })
      if (!response.ok) throw new Error(await getApiError(response))

      const blob = await response.blob()
      const disposition = response.headers.get('Content-Disposition') || ''
      const encodedName = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1]
      const plainName = disposition.match(/filename="?([^";]+)"?/i)?.[1]
      const downloadName = encodedName
        ? decodeURIComponent(encodedName)
        : plainName || 'ficha.docx'
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = downloadName
      link.click()
      window.setTimeout(() => URL.revokeObjectURL(url), 1000)
      setDownloaded(true)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'No se pudo generar el documento Word.')
    } finally {
      setGenerating(false)
    }
  }

  if (loading) {
    return <main className="flex min-h-screen items-center justify-center bg-[#222] text-slate-300">Cargando información…</main>
  }

  if (!ficha) {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-[#222] px-6 text-center text-slate-200">
        <FileText className="size-10 text-[#55a7d8]" />
        <h1 className="text-xl font-semibold text-white">No hay información para revisar</h1>
        <p role={error ? 'alert' : undefined} className="max-w-lg text-sm text-slate-400">{error || 'Cargue primero un PDF para extraer sus datos.'}</p>
        <Button nativeButton={false} render={<a href="/" />} className="bg-[#00508C] text-white hover:bg-[#0068b5]"><ArrowLeft data-icon="inline-start" /> Volver a cargar</Button>
      </main>
    )
  }

  const familyLists: { key: FamiliarListKey; label: string }[] = [
    { key: 'hermanos', label: 'Hermanos' },
    { key: 'hermanas', label: 'Hermanas' },
    { key: 'hijos', label: 'Hijos' },
    { key: 'hijas', label: 'Hijas' },
  ]

  return (
    <main className="min-h-screen bg-[#222222] text-slate-100">
      <header className="border-b border-white/10">
        <div className="mx-auto flex max-w-[1800px] items-center justify-between gap-4 px-6 py-5 lg:px-8">
          <div className="flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-md bg-[#00508C]"><FileText className="size-5 text-white" /></div>
            <div><p className="text-sm font-semibold text-white">Sistema de Identificación</p><p className="text-xs text-slate-400">Revisión y edición de ficha</p></div>
          </div>
          <Button nativeButton={false} render={<a href="/" />} variant="ghost" className="text-slate-300 hover:bg-white/10 hover:text-white"><ArrowLeft data-icon="inline-start" /> Volver</Button>
        </div>
      </header>

      <div className="mx-auto max-w-[1800px] px-4 py-6 lg:px-6">
        <div className="grid items-start gap-6 md:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)] xl:gap-8">
          <aside className="min-w-0 rounded-lg border border-white/10 bg-[#2b2b2b] p-4 md:sticky md:top-4 md:h-[calc(100vh-2rem)]">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div className="flex min-w-0 items-center gap-2">
                <FileText className="size-4 shrink-0 text-[#63b5e9]" />
                <h2 className="truncate text-sm font-medium text-white">PDF original</h2>
              </div>
              {pdfUrl && (
                <a href={pdfUrl} target="_blank" rel="noreferrer" className="shrink-0 text-xs text-[#75c3f1] hover:underline">
                  Abrir aparte
                </a>
              )}
            </div>
            <p className="mb-3 truncate text-xs text-slate-400" title={fileName}>{fileName}</p>
            {pdfUrl ? (
              <iframe
                title={`Vista previa del PDF ${fileName}`}
                src={pdfUrl}
                className="h-[55vh] w-full rounded border border-white/10 bg-white md:h-[calc(100%-3.5rem)]"
              />
            ) : (
              <div className="flex h-[55vh] items-center justify-center rounded border border-white/10 bg-[#222] px-5 text-center text-sm text-slate-400 md:h-[calc(100%-3.5rem)]">
                No se encontró el PDF original. Vuelva a cargar el archivo para revisar sus páginas.
              </div>
            )}
          </aside>

          <section className="min-w-0">
        <div className="mb-7">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#55a7d8]">Revisión antes de generar</p>
          <h1 className="mt-2 text-2xl font-semibold text-white sm:text-3xl">Verifique la información extraída</h1>
          <p className="mt-2 text-sm text-slate-400">Revise y corrija los campos; los cambios se usarán para generar la ficha Word. PDF de origen: {fileName}</p>
        </div>

        {validacion?.incidencias.length ? (
          <div className="mb-6 rounded-md border border-amber-400/30 bg-amber-400/5 p-4">
            <h2 className="mb-2 font-medium text-amber-200">Observaciones de la extracción</h2>
            <ul className="space-y-1.5 text-sm text-slate-300">
              {validacion.incidencias.map((item, index) => (
                <li key={`${item.campo}-${index}`} className="flex gap-2">
                  <span className={item.nivel === 'error' ? 'text-red-300' : 'text-amber-200'}>{item.nivel === 'error' ? 'Error' : 'Aviso'}:</span>
                  <span>{item.campo} — {item.mensaje}</span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        <div className="space-y-5">
          <Panel title="Datos generales">
            <div className="grid gap-4 sm:grid-cols-2">
              <InputField label="Fecha de elaboración" type="date" value={ficha.fecha} onChange={(value) => setFicha({ ...ficha, fecha: value })} />
              <InputField label="NUC del encabezado" value={ficha.nuc} onChange={(value) => setFicha({ ...ficha, nuc: value || null })} />
              <div className="sm:col-span-2"><TextAreaField label="Observaciones" value={ficha.observaciones} onChange={(value) => setFicha({ ...ficha, observaciones: value || null })} /></div>
            </div>
          </Panel>

          <Panel title="Datos personales">
            <div className="grid gap-4 sm:grid-cols-2">
              <InputField label="Nombre completo" value={ficha.datos_personales.nombre} onChange={(value) => updatePersonal('nombre', value || null)} />
              <InputField label="Fecha de nacimiento" type="date" value={ficha.datos_personales.fecha_nacimiento} onChange={(value) => updatePersonal('fecha_nacimiento', value || null)} />
              <InputField label="Lugar de nacimiento" value={ficha.datos_personales.lugar_nacimiento} onChange={(value) => updatePersonal('lugar_nacimiento', value || null)} />
              <InputField label="Estado" value={ficha.datos_personales.estado} onChange={(value) => updatePersonal('estado', value || 'Chihuahua')} />
              <InputField label="Edad" type="number" value={ficha.datos_personales.edad} onChange={(value) => updatePersonal('edad', value ? Number(value) : null)} />
              <InputField label="Ocupación" value={ficha.datos_personales.ocupacion} onChange={(value) => updatePersonal('ocupacion', value || null)} />
              <InputField label="Estado civil" value={ficha.datos_personales.estado_civil} onChange={(value) => updatePersonal('estado_civil', value || null)} />
              <InputField label="Alias" value={ficha.datos_personales.alias} onChange={(value) => updatePersonal('alias', value || null)} />
              <div className="sm:col-span-2">
                <StringList title="Domicilios" items={ficha.datos_personales.domicilios} onChange={(items) => updatePersonal('domicilios', items)} />
              </div>
              <div className="sm:col-span-2">
                <StringList title="Teléfonos" items={ficha.datos_personales.telefonos} onChange={(items) => updatePersonal('telefonos', items)} />
              </div>
              <InputField label="Teléfono de emergencia" value={ficha.datos_personales.telefono_emergencia} onChange={(value) => updatePersonal('telefono_emergencia', value || null)} />
            </div>
          </Panel>

          <Panel title="Datos familiares">
            <div className="mb-4 grid gap-4 sm:grid-cols-3">
              <InputField label="Madre" value={ficha.datos_familiares.madre} onChange={(value) => updateFamily('madre', value || null)} />
              <InputField label="Padre" value={ficha.datos_familiares.padre} onChange={(value) => updateFamily('padre', value || null)} />
              <InputField label="Pareja" value={ficha.datos_familiares.pareja} onChange={(value) => updateFamily('pareja', value || null)} />
            </div>
            <div className="space-y-4">
              {familyLists.map(({ key, label }) => (
                <div
                  key={key}
                  onDragOver={(event) => {
                    if (draggedFamiliar && familyDestination[draggedFamiliar.key] === key) {
                      event.preventDefault()
                      event.dataTransfer.dropEffect = 'move'
                    }
                  }}
                  onDrop={(event) => dropFamiliar(event, key)}
                  className={`rounded-md border p-4 transition ${
                    draggedFamiliar && familyDestination[draggedFamiliar.key] === key
                      ? 'border-dashed border-[#75c3f1] bg-[#00508C]/10'
                      : 'border-white/10'
                  }`}
                >
                  <div className="mb-3 flex items-center justify-between"><h3 className="text-sm font-medium text-white">{label}</h3><AddButton label="Agregar" onClick={() => updateFamily(key, [...ficha.datos_familiares[key], emptyFamiliar()])} /></div>
                  {draggedFamiliar && familyDestination[draggedFamiliar.key] === key && (
                    <p className="mb-3 text-xs text-[#9bd8ff]">Suelta aquí para mover a {label.toLowerCase()}.</p>
                  )}
                  {ficha.datos_familiares[key].length ? ficha.datos_familiares[key].map((person, index) => (
                    <div
                      key={`${key}-${index}`}
                      draggable
                      title="Arrastra este registro a su sección correspondiente"
                      onDragStart={(event) => startDraggingFamiliar(event, key, index)}
                      onDragEnd={() => setDraggedFamiliar(null)}
                      className="mb-3 flex cursor-grab items-end gap-2 last:mb-0 active:cursor-grabbing"
                    >
                      <div className="grid min-w-0 flex-1 gap-3 sm:grid-cols-2">
                        <InputField label="Nombre" value={person.nombre} onChange={(value) => updateFamiliar(key, index, { nombre: value })} />
                        <InputField label="Fecha de nacimiento" type="date" value={person.fecha_nacimiento} onChange={(value) => updateFamiliar(key, index, { fecha_nacimiento: value || null })} />
                      </div>
                      <RemoveButton label={`Quitar ${label.toLowerCase()}`} onClick={() => updateFamily(key, ficha.datos_familiares[key].filter((_, i) => i !== index))} />
                    </div>
                  )) : <p className="text-sm text-slate-500">Sin registros.</p>}
                </div>
              ))}
            </div>
          </Panel>

          <Panel title="Carpetas de investigación" action={<AddButton label="Agregar carpeta" onClick={() => setFicha({ ...ficha, carpetas: [...ficha.carpetas, emptyCarpeta()] })} />}>
            {ficha.carpetas.length ? <div className="space-y-4">{ficha.carpetas.map((item, index) => (
              <div key={`carpeta-${index}`} className="rounded-md border border-white/10 p-4">
                <div className="mb-3 flex items-center justify-between"><h3 className="text-sm font-medium text-white">Carpeta {index + 1}</h3><RemoveButton label="Quitar carpeta" onClick={() => setFicha({ ...ficha, carpetas: ficha.carpetas.filter((_, i) => i !== index) })} /></div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <InputField label="NUC" value={item.nuc} onChange={(value) => updateCarpeta(index, { nuc: value || null })} />
                  <InputField label="Fecha de inicio" type="date" value={item.fecha_inicio} onChange={(value) => updateCarpeta(index, { fecha_inicio: value || null })} />
                  <InputField label="Delito" value={item.delito} onChange={(value) => updateCarpeta(index, { delito: value || null })} />
                  <InputField label="Calidad" value={item.calidad} onChange={(value) => updateCarpeta(index, { calidad: value || null })} />
                  <InputField label="Unidad" value={item.unidad} onChange={(value) => updateCarpeta(index, { unidad: value || null })} />
                  <div className="sm:col-span-2"><TextAreaField label="Hechos" value={item.hechos} onChange={(value) => updateCarpeta(index, { hechos: value || null })} /></div>
                </div>
              </div>
            ))}</div> : <p className="text-sm text-slate-500">Sin carpetas registradas.</p>}
          </Panel>

          <Panel title="Datos vehiculares" action={<AddButton label="Agregar vehículo" onClick={() => setFicha({ ...ficha, vehiculos: [...ficha.vehiculos, emptyVehiculo()] })} />}>
            {ficha.vehiculos.length ? <div className="space-y-4">{ficha.vehiculos.map((item, index) => (
              <div key={`vehiculo-${index}`} className="rounded-md border border-white/10 p-4">
                <div className="mb-3 flex items-center justify-between"><h3 className="text-sm font-medium text-white">Vehículo {index + 1}</h3><RemoveButton label="Quitar vehículo" onClick={() => setFicha({ ...ficha, vehiculos: ficha.vehiculos.filter((_, i) => i !== index) })} /></div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <InputField label="Fecha de alta" value={item.alta} onChange={(value) => updateVehiculo(index, { alta: value || null })} />
                  <InputField label="Marca" value={item.marca} onChange={(value) => updateVehiculo(index, { marca: value || null })} />
                  <InputField label="Línea" value={item.linea} onChange={(value) => updateVehiculo(index, { linea: value || null })} />
                  <InputField label="Modelo" value={item.modelo} onChange={(value) => updateVehiculo(index, { modelo: value || null })} />
                  <InputField label="Placa" value={item.placa} onChange={(value) => updateVehiculo(index, { placa: value || null })} />
                  <InputField label="Número de serie" value={item.serie} onChange={(value) => updateVehiculo(index, { serie: value || null })} />
                </div>
              </div>
            ))}</div> : <p className="text-sm text-slate-500">Sin vehículos registrados.</p>}
          </Panel>

          <Panel title="Registro público">
            <StringList title="Registros" items={ficha.registro_publico} onChange={(items) => setFicha({ ...ficha, registro_publico: items })} />
          </Panel>

          <Panel title="Fuentes abiertas" action={<AddButton label="Agregar fuente" onClick={() => setFicha({ ...ficha, fuentes_abiertas: [...ficha.fuentes_abiertas, emptyFuente()] })} />}>
            {ficha.fuentes_abiertas.length ? <div className="space-y-4">{ficha.fuentes_abiertas.map((item, index) => (
              <div key={`fuente-${index}`} className="rounded-md border border-white/10 p-4">
                <div className="mb-3 flex items-center justify-between"><h3 className="text-sm font-medium text-white">Fuente {index + 1}</h3><RemoveButton label="Quitar fuente" onClick={() => setFicha({ ...ficha, fuentes_abiertas: ficha.fuentes_abiertas.filter((_, i) => i !== index) })} /></div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="sm:col-span-2"><TextAreaField label="Descripción" value={item.descripcion} onChange={(value) => updateFuente(index, { descripcion: value })} rows={2} /></div>
                  <InputField label="Fecha de consulta" value={item.fecha_consulta} onChange={(value) => updateFuente(index, { fecha_consulta: value || null })} />
                  <InputField label="Enlace" value={item.link} onChange={(value) => updateFuente(index, { link: value || null })} />
                </div>
              </div>
            ))}</div> : <p className="text-sm text-slate-500">Sin fuentes abiertas registradas.</p>}
          </Panel>

          <Panel title="Fotografías" action={<AddButton label="Agregar referencia" onClick={() => setFicha({ ...ficha, fotografias: [...ficha.fotografias, emptyFotografia()] })} />}>
            {ficha.foto_base64 && (
              <div className="mb-5 grid gap-4 md:grid-cols-2">
                <figure className="flex flex-col items-center rounded-md border border-white/10 bg-[#222] p-4">
                  <img
                    src={`data:image/png;base64,${ficha.foto_base64}`}
                    alt={`Fotografía principal de ${ficha.datos_personales.nombre || 'la persona identificada'}`}
                    className="max-h-80 max-w-full rounded object-contain"
                  />
                  <figcaption className="mt-3 text-xs text-slate-400">Fotografía principal extraída del PDF; se incluirá en el Word.</figcaption>
                </figure>
                <TextAreaField
                  label="Nota junto a la fotografía"
                  value={ficha.nota_fotografia}
                  onChange={(value) => setFicha({ ...ficha, nota_fotografia: value || null })}
                />
              </div>
            )}
            {ficha.fotografias.length ? <div className="space-y-4">{ficha.fotografias.map((item, index) => (
              <div key={`foto-${index}`} className="rounded-md border border-white/10 p-4">
                <div className="mb-3 flex items-center justify-between"><h3 className="text-sm font-medium text-white">Referencia {index + 1}</h3><RemoveButton label="Quitar referencia" onClick={() => setFicha({ ...ficha, fotografias: ficha.fotografias.filter((_, i) => i !== index) })} /></div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <InputField label="Fuente" value={item.fuente} onChange={(value) => updateFotografia(index, { fuente: value || null })} />
                  <InputField label="Fecha" type="date" value={item.fecha} onChange={(value) => updateFotografia(index, { fecha: value || null })} />
                  <InputField label="Nombre" value={item.nombre} onChange={(value) => updateFotografia(index, { nombre: value || null })} />
                  <InputField label="Número de causa" value={item.numero_causa} onChange={(value) => updateFotografia(index, { numero_causa: value || null })} />
                </div>
              </div>
            ))}</div> : <p className="text-sm text-slate-500">Sin referencias fotográficas registradas.</p>}
            {!ficha.foto_base64 && !ficha.fotografias.length && <p className="text-sm text-slate-500">No se encontraron fotografías en el PDF.</p>}
          </Panel>
        </div>

        <div className="sticky bottom-0 mt-6 flex flex-col gap-3 border-t border-white/10 bg-[#222]/95 py-4 backdrop-blur sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0">
            {error && <p role="alert" className="whitespace-pre-line text-sm text-red-300">{error}</p>}
            {downloaded && <p role="status" className="text-sm text-emerald-300">El documento Word se descargó correctamente.</p>}
          </div>
          <Button type="button" disabled={generating} onClick={handleGenerate} className="shrink-0 bg-[#00508C] text-white hover:bg-[#0068b5] disabled:bg-slate-700">
            {generating ? <><FilePlus2 data-icon="inline-start" /> Generando…</> : <><Download data-icon="inline-start" /> Generar y descargar Word</>}
          </Button>
        </div>
          </section>
        </div>
      </div>
    </main>
  )
}

function StringList({ title, items, onChange }: { title: string; items: string[]; onChange: (items: string[]) => void }) {
  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-medium text-slate-200">{title}</h3>
        <AddButton label="Agregar" onClick={() => onChange([...items, ''])} />
      </div>
      {items.length ? <div className="space-y-2">
        {items.map((item, index) => (
          <div key={`${title}-${index}`} className="flex items-center gap-2">
            <input value={item} onChange={(event) => onChange(items.map((current, i) => i === index ? event.target.value : current))} className="w-full rounded-md border border-white/10 bg-[#222] px-3 py-2.5 text-sm text-white outline-none focus:border-[#55a7d8] focus:ring-1 focus:ring-[#55a7d8]" />
            <RemoveButton label={`Quitar ${title.toLowerCase()}`} onClick={() => onChange(items.filter((_, i) => i !== index))} />
          </div>
        ))}
      </div> : <p className="text-sm text-slate-500">Sin registros.</p>}
    </div>
  )
}
