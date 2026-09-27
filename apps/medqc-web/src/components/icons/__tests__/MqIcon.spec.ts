import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import MqIcon from '../MqIcon.vue'
import MqIconTile from '../MqIconTile.vue'
import { MQ_ICONS, type MqIconName } from '../mqIcons'

const names = Object.keys(MQ_ICONS) as MqIconName[]

describe('MqIcon 定制图标', () => {
  it.each(names)('%s 渲染为非空 SVG', (name) => {
    const wrapper = mount(MqIcon, { props: { name, size: 20, color: '#0A6CFF' } })
    const svg = wrapper.find('svg')
    expect(svg.attributes('width')).toBe('20')
    expect(svg.attributes('aria-hidden')).toBe('true')
    expect(svg.findAll('path, circle').length).toBeGreaterThan(0)
  })

  it('徽章图标带白色标记', () => {
    const wrapper = mount(MqIcon, { props: { name: 'fp_qc' } })
    expect(wrapper.find('circle[r="4.6"]').exists()).toBe(true)
    expect(wrapper.findAll('[stroke="#FFFFFF"]').length).toBeGreaterThan(0)
  })
})

describe('MqIconTile 图标底座', () => {
  it('按色调渲染图标颜色与尺寸', () => {
    const wrapper = mount(MqIconTile, { props: { name: 'pool', tone: 'brand', size: 40 } })
    const tile = wrapper.find('.mq-icon-tile')
    expect(tile.attributes('style')).toContain('width: 40px')
    expect(wrapper.find('svg').attributes('width')).toBe('25')
    expect(wrapper.find('path[fill="#0A6CFF"]').exists()).toBe(true)
  })
})
