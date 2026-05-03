import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import Step9Listing from './Step9Listing.vue'

function mountStep9(overrides = {}) {
  return mount(Step9Listing, {
    props: {
      listingHints: { industryRaw: '涂料/油漆行业', priceFromManifest: null },
      industry: '涂料/油漆行业',
      industryOptions: ['涂料/油漆行业', '考勤/人事行业'],
      price: 0,
      error: '',
      success: '',
      uploading: false,
      canConfirm: true,
      isCatalogEdit: false,
      ...overrides,
    },
  })
}

describe('Step9Listing', () => {
  it('renders AI and manifest industries as selectable options', () => {
    const wrapper = mountStep9()
    const labels = wrapper.findAll('select option').map((option) => option.text())

    expect(labels).toContain('涂料/油漆行业')
    expect(labels).toContain('考勤/人事行业')
    expect(labels).toContain('通用')
  })

  it('keeps custom industry editable', async () => {
    const wrapper = mountStep9({ industry: '低空经济行业', industryOptions: ['涂料/油漆行业'] })
    const input = wrapper.find('input.industry-custom')

    await input.setValue('低空经济行业')

    const events = wrapper.emitted('update:industry') || []
    expect(events[events.length - 1]?.[0]).toBe('低空经济行业')
    expect(wrapper.find('select').text()).toContain('低空经济行业')
  })
})
