export const API_BASE_URL = (process.env.NEXT_PUBLIC_API_URL || 'https://archiva-gob-backend.vercel.app').replace(/\/+$/, '')

export async function getApiError(response: Response): Promise<string> {
  const body: unknown = await response.json().catch(() => null)
  if (typeof body === 'object' && body !== null && 'detail' in body) {
    const detail = body.detail
    if (typeof detail === 'string') return detail
    if (typeof detail === 'object' && detail !== null && 'mensaje' in detail && typeof detail.mensaje === 'string') {
      const incidencias = 'incidencias' in detail && Array.isArray(detail.incidencias)
        ? detail.incidencias
            .map((item: { campo?: string; mensaje?: string }) => `${item.campo ? `${item.campo}: ` : ''}${item.mensaje || ''}`)
            .filter(Boolean)
        : []
      return [detail.mensaje, ...incidencias].join('\n')
    }
  }
  return 'Ocurrió un error al comunicarse con el backend.'
}
