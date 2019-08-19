/* global describe, it, expect */
import { supportedLocales } from './locales'
import fetchCatalog from './catalogs'

describe('i18n helpers', () => {
  describe('message catalogs', () => {
    it.each(Object.keys(supportedLocales))('%s should have a valid catalog', (locale) => {
      const catalog = fetchCatalog(locale)
      expect(catalog).toBeDefined()
      expect(catalog.messages).toBeDefined()
      expect(Object.keys(catalog.messages)).not.toHaveLength(0)
      expect(catalog.languageData).toBeDefined()
    })
  })
})
