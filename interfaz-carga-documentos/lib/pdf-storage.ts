const DATABASE_NAME = 'identification-documents'
const STORE_NAME = 'uploads'
const PDF_KEY = 'source-pdf'

function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DATABASE_NAME, 1)
    request.onupgradeneeded = () => {
      request.result.createObjectStore(STORE_NAME)
    }
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error || new Error('No se pudo abrir el almacenamiento del PDF.'))
    request.onblocked = () => reject(new Error('El almacenamiento del PDF está bloqueado por otra pestaña.'))
  })
}

export async function saveSourcePdf(file: File): Promise<void> {
  const database = await openDatabase()
  try {
    await new Promise<void>((resolve, reject) => {
      const transaction = database.transaction(STORE_NAME, 'readwrite')
      transaction.objectStore(STORE_NAME).put(file, PDF_KEY)
      transaction.oncomplete = () => resolve()
      transaction.onerror = () => reject(transaction.error || new Error('No se pudo guardar el PDF para revisión.'))
      transaction.onabort = () => reject(transaction.error || new Error('Se canceló el guardado del PDF.'))
    })
  } finally {
    database.close()
  }
}

export async function loadSourcePdf(): Promise<Blob | null> {
  const database = await openDatabase()
  try {
    return await new Promise<Blob | null>((resolve, reject) => {
      const transaction = database.transaction(STORE_NAME, 'readonly')
      const request = transaction.objectStore(STORE_NAME).get(PDF_KEY)
      request.onsuccess = () => resolve(request.result instanceof Blob ? request.result : null)
      request.onerror = () => reject(request.error || new Error('No se pudo recuperar el PDF original.'))
    })
  } finally {
    database.close()
  }
}
