import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ReviewForm from './ReviewForm.vue'

describe('ReviewForm', () => {
  it('emits message and code updates and submit', async () => {
    const wrapper = mount(ReviewForm, {
      props: {
        message: 'm1',
        code: 'c1',
        submitting: false,
      },
    })

    const areas = wrapper.findAll('textarea')
    await areas[0].setValue('new message')
    await areas[1].setValue('new code')
    await wrapper.find('button').trigger('click')

    expect(wrapper.emitted('update:message')?.[0]).toEqual(['new message'])
    expect(wrapper.emitted('update:code')?.[0]).toEqual(['new code'])
    expect(wrapper.emitted('submit')).toBeTruthy()
  })
})
