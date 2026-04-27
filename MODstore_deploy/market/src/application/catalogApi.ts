import { requestJson } from '../infrastructure/http/client'
import type { CatalogItem } from '../domain/catalog/types'

export function listCatalog(limit = 50, offset = 0): Promise<{ items: CatalogItem[]; total?: number }> {
  return requestJson(`/api/market/catalog?limit=${limit}&offset=${offset}`)
}
