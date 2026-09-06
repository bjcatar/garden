/**
 * Local Contributions — GitHub-style heatmap of git commits on this machine.
 *
 * Save path: ~/.hermes/desktop-plugins/local-contrib/plugin.js
 * Backend:   ~/.hermes/plugins/local-contrib  (enable with `hermes plugins enable local-contrib`)
 *
 * Plain ESM, uncompiled — UI is jsx() calls, not JSX syntax.
 */
import {
  cn,
  Codicon,
  EmptyState,
  ErrorState,
  GlyphSpinner,
  haptic,
  host,
  PALETTE_AREA,
  queryClient,
  ROUTES_AREA,
  ScrollArea,
  SIDEBAR_NAV_AREA,
  Tip,
  useQuery
} from '@hermes/plugin-sdk'
import { useMemo, useState } from 'react'
import { jsx, jsxs } from 'react/jsx-runtime'

const ID = 'local-contrib'
const PATH = '/local-contrib'
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const WEEKDAY_LABELS = ['', 'Mon', '', 'Wed', '', 'Fri', '']

let pluginCtx = null

function isoLocal(d) {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function parseIso(iso) {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d)
}

function prettyDate(iso) {
  return parseIso(iso).toLocaleDateString(undefined, {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  })
}

function plural(n, word) {
  return `${n} ${word}${n === 1 ? '' : 's'}`
}

function levelFor(count, cuts) {
  if (!count) return 0
  if (count <= cuts[0]) return 1
  if (count <= cuts[1]) return 2
  if (count <= cuts[2]) return 3
  return 4
}

function cutsFromCounts(counts) {
  const nz = counts.filter(c => c > 0).sort((a, b) => a - b)
  if (!nz.length) return [1, 2, 4]
  const at = p => nz[Math.min(nz.length - 1, Math.max(0, Math.ceil(p * nz.length) - 1))]
  const a = Math.max(1, at(0.35))
  const b = Math.max(a + 1, at(0.65))
  const c = Math.max(b + 1, at(0.9))
  return [a, b, c]
}

function cellBackground(level, inRange) {
  if (!inRange) return 'transparent'
  if (level === 0) {
    return 'color-mix(in srgb, var(--ui-text-quaternary) 16%, transparent)'
  }
  const mix = [0, 30, 52, 74, 100][level]
  return `color-mix(in srgb, var(--ui-accent) ${mix}%, transparent)`
}

function buildWeeks(startIso, endIso, days) {
  const start = parseIso(startIso)
  const end = parseIso(endIso)
  const cursor = new Date(start)
  cursor.setDate(cursor.getDate() - cursor.getDay())
  const weeks = []
  while (weeks.length < 54) {
    const week = []
    for (let i = 0; i < 7; i++) {
      const iso = isoLocal(cursor)
      const inRange = cursor >= start && cursor <= end
      const cell = inRange ? days[iso] : null
      week.push({
        date: iso,
        inRange,
        commits: cell?.commits || 0,
        additions: cell?.additions || 0,
        deletions: cell?.deletions || 0
      })
      cursor.setDate(cursor.getDate() + 1)
    }
    weeks.push(week)
    if (cursor > end) break
  }
  return weeks
}

function monthLabels(weeks) {
  const labels = []
  let last = -1
  weeks.forEach((week, index) => {
    const first = week.find(c => c.inRange)
    if (!first) return
    const month = parseIso(first.date).getMonth()
    if (month !== last) {
      labels.push({ index, month })
      last = month
    }
  })
  return labels
}

function useHeatmap(year) {
  return useQuery({
    queryFn: () => {
      const q = year == null ? '/heatmap' : `/heatmap?year=${year}`
      return pluginCtx.rest(q)
    },
    queryKey: [ID, 'heatmap', year == null ? 'rolling' : year],
    refetchInterval: 120_000,
    retry: 1
  })
}

function HeatmapGrid({ weeks, cuts, selected, onSelect }) {
  const labels = monthLabels(weeks)
  const cell = 11
  const gap = 3
  const labelW = 28
  const monthH = 18
  const width = labelW + weeks.length * (cell + gap)

  return jsxs('div', {
    className: 'inline-block max-w-full overflow-x-auto pb-1',
    children: [
      jsxs('div', {
        className: 'relative',
        style: { width, paddingLeft: labelW },
        children: [
          jsx('div', {
            className: 'relative mb-1 text-[10px] text-(--ui-text-quaternary)',
            style: { height: monthH },
            children: labels.map(l =>
              jsx(
                'span',
                {
                  className: 'absolute left-0',
                  style: { left: l.index * (cell + gap) },
                  children: MONTHS[l.month]
                },
                `${l.month}-${l.index}`
              )
            )
          }),
          jsxs('div', {
            className: 'flex',
            children: [
              jsx('div', {
                className: 'flex flex-col text-[10px] leading-[11px] text-(--ui-text-quaternary)',
                style: {
                  width: labelW,
                  marginLeft: -labelW,
                  gap,
                  paddingTop: 0
                },
                children: WEEKDAY_LABELS.map((label, i) =>
                  jsx(
                    'div',
                    {
                      className: 'flex items-center justify-end pr-1',
                      style: { height: cell },
                      children: label
                    },
                    i
                  )
                )
              }),
              jsx('div', {
                className: 'flex',
                style: { gap },
                children: weeks.map((week, wi) =>
                  jsx(
                    'div',
                    {
                      className: 'flex flex-col',
                      style: { gap },
                      children: week.map(day => {
                        const level = levelFor(day.commits, cuts)
                        const isSel = selected === day.date
                        return jsx(
                          'button',
                          {
                            type: 'button',
                            disabled: !day.inRange,
                            title: day.inRange
                              ? `${plural(day.commits, 'contribution')} on ${prettyDate(day.date)}`
                              : undefined,
                            onClick: () => {
                              if (!day.inRange) return
                              haptic('tap')
                              onSelect(day.date)
                            },
                            className: cn(
                              'rounded-[2px] p-0 transition-[box-shadow,transform]',
                              day.inRange && 'hover:ring-1 hover:ring-(--ui-text-tertiary)',
                              isSel && 'ring-1 ring-(--ui-accent)'
                            ),
                            style: {
                              width: cell,
                              height: cell,
                              background: cellBackground(level, day.inRange),
                              cursor: day.inRange ? 'pointer' : 'default'
                            }
                          },
                          day.date
                        )
                      })
                    },
                    wi
                  )
                )
              })
            ]
          })
        ]
      }),
      jsxs('div', {
        className: 'mt-2 flex items-center justify-end gap-1 text-[10px] text-(--ui-text-quaternary)',
        children: [
          jsx('span', { children: 'Less' }),
          [0, 1, 2, 3, 4].map(level =>
            jsx(
              'span',
              {
                className: 'inline-block rounded-[2px]',
                style: {
                  width: cell,
                  height: cell,
                  background: cellBackground(level, true)
                }
              },
              level
            )
          ),
          jsx('span', { children: 'More' })
        ]
      })
    ]
  })
}

function YearRail({ years, year, onPick }) {
  const items = [{ key: 'rolling', label: 'Last year', value: null }, ...years.map(y => ({ key: String(y), label: String(y), value: y }))]
  return jsx('div', {
    className: 'flex w-[7.5rem] shrink-0 flex-col gap-1',
    children: items.map(item => {
      const active = year === item.value || (item.value == null && year == null)
      return jsx(
        'button',
        {
          type: 'button',
          onClick: () => {
            haptic('tap')
            onPick(item.value)
          },
          className: cn(
            'rounded-md px-3 py-1.5 text-left text-[13px] transition-colors',
            active
              ? 'bg-(--chrome-action-hover) text-foreground ring-1 ring-(--ui-accent)'
              : 'text-(--ui-text-secondary) hover:bg-(--chrome-action-hover)'
          ),
          children: item.label
        },
        item.key
      )
    })
  })
}

function DayPanel({ date }) {
  const q = useQuery({
    enabled: Boolean(date) && Boolean(pluginCtx),
    queryFn: () => pluginCtx.rest(`/day?date=${date}`),
    queryKey: [ID, 'day', date],
    retry: 1
  })

  if (!date) {
    return jsx('div', {
      className: 'text-sm text-(--ui-text-tertiary)',
      children: 'Click a day to see what landed on this machine.'
    })
  }

  if (q.isLoading) {
    return jsx('div', { className: 'flex items-center gap-2 text-sm text-(--ui-text-tertiary)', children: jsx(GlyphSpinner, {}) })
  }

  const data = q.data || {}
  const entries = data.entries || []

  return jsxs('div', {
    className: 'flex flex-col gap-3',
    children: [
      jsxs('div', {
        children: [
          jsx('div', { className: 'text-sm font-medium', children: prettyDate(date) }),
          jsx('div', {
            className: 'mt-0.5 text-xs text-(--ui-text-tertiary)',
            children: `${plural(data.commits || 0, 'contribution')} · +${data.additions || 0} / −${data.deletions || 0}`
          })
        ]
      }),
      entries.length === 0
        ? jsx('div', { className: 'text-sm text-(--ui-text-tertiary)', children: 'Quiet day — no commits matched.' })
        : jsx('div', {
            className: 'flex flex-col gap-1.5',
            children: entries.map(entry =>
              jsxs(
                'div',
                {
                  className: 'flex items-start gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-(--chrome-action-hover)',
                  children: [
                    jsx('span', {
                      className: 'mt-0.5 font-mono text-[11px] text-(--ui-text-quaternary)',
                      children: entry.hash?.slice(0, 7)
                    }),
                    jsxs('div', {
                      className: 'min-w-0 flex-1',
                      children: [
                        jsx('div', { className: 'truncate', children: entry.subject }),
                        jsx('div', {
                          className: 'truncate text-[11px] text-(--ui-text-quaternary)',
                          children: `${entry.repo} · +${entry.additions} / −${entry.deletions}`
                        })
                      ]
                    })
                  ]
                },
                entry.hash + entry.repo
              )
            )
          })
    ]
  })
}

function GardenPage() {
  const [year, setYear] = useState(null)
  const [selected, setSelected] = useState(null)
  const q = useHeatmap(year)
  const data = q.data

  const weeks = useMemo(() => {
    if (!data?.range) return []
    return buildWeeks(data.range.start, data.range.end, data.days || {})
  }, [data])

  const cuts = useMemo(() => {
    const counts = weeks.flat().filter(c => c.inRange).map(c => c.commits)
    return cutsFromCounts(counts)
  }, [weeks])

  const title = data
    ? data.mode === 'year'
      ? `${data.total} contributions in ${data.year}`
      : `${data.total} contributions in the last year`
    : 'Contributions'

  const repoLine = (data?.repos || [])
    .filter(r => r.commits > 0)
    .map(r => `${r.name} (${r.commits})`)
    .join(' · ')

  return jsx(ScrollArea, {
    className: 'h-full',
    children: jsxs('div', {
      className: 'mx-auto flex w-full max-w-[980px] flex-col gap-6 px-6 py-6',
      children: [
        jsxs('div', {
          className: 'flex items-start justify-between gap-3',
          children: [
            jsxs('div', {
              children: [
                jsx('h1', { className: 'text-lg font-medium tracking-tight', children: title }),
                jsx('p', {
                  className: 'mt-1 max-w-[42rem] text-xs text-(--ui-text-tertiary)',
                  children: repoLine
                    ? `Local git on this Omarchy machine · ${repoLine}`
                    : 'Local git commits authored on this Omarchy machine — same shape as GitHub, counted here, not in the cloud.'
                })
              ]
            }),
            jsx('button', {
              type: 'button',
              disabled: q.isFetching,
              className: cn(
                'rounded-md px-2 py-1 text-xs text-(--ui-text-tertiary) transition-colors',
                'hover:bg-(--chrome-action-hover) hover:text-foreground disabled:opacity-50'
              ),
              onClick: () => {
                haptic('tap')
                queryClient.invalidateQueries({ queryKey: [ID] })
                pluginCtx
                  ?.rest('/heatmap?refresh=true')
                  .then(() => queryClient.invalidateQueries({ queryKey: [ID] }))
                  .catch(() => undefined)
              },
              children: q.isFetching ? 'Scanning…' : 'Refresh'
            })
          ]
        }),
        q.isLoading
          ? jsx('div', { className: 'flex h-40 items-center justify-center', children: jsx(GlyphSpinner, {}) })
          : q.isError
            ? jsx(ErrorState, {
                title: 'Could not load local contributions',
                description: 'The git scanner is a Python plugin. It is already enabled on this machine; restart Hermes once so the gateway mounts /api/plugins/local-contrib, then reopen Garden.'
              })
            : !data || data.total === 0
              ? jsx(EmptyState, {
                  title: 'No local contributions yet',
                  description: 'Scanning ~/Projects and ~/Documents. Clone or commit in those trees and this garden fills in — one square per day, colored by volume.'
                })
              : jsxs('div', {
                  className: 'flex flex-col gap-6',
                  children: [
                    jsxs('div', {
                      className: 'flex items-start gap-4',
                      children: [
                        jsx('div', {
                          className: 'min-w-0 flex-1 rounded-lg border border-(--ui-stroke-secondary) p-4',
                          children: jsx(HeatmapGrid, {
                            weeks,
                            cuts,
                            selected,
                            onSelect: setSelected
                          })
                        }),
                        jsx(YearRail, {
                          years: data.years || [],
                          year,
                          onPick: next => {
                            setYear(next)
                            setSelected(null)
                          }
                        })
                      ]
                    }),
                    jsxs('div', {
                      children: [
                        jsx('h2', {
                          className: 'mb-3 text-sm font-medium',
                          children: 'Contribution activity'
                        }),
                        jsx(DayPanel, { date: selected })
                      ]
                    })
                  ]
                })
      ]
    })
  })
}

function TodayChip() {
  const q = useHeatmap(null)
  const n = q.data?.today?.commits
  return jsx(Tip, {
    label: n == null ? 'Local contributions' : `${plural(n, 'contribution')} today — open garden`,
    children: jsxs('button', {
      type: 'button',
      className: cn(
        'inline-flex h-full items-center gap-1 px-1.5 text-[0.6875rem] tabular-nums transition-colors',
        'text-(--ui-text-tertiary) hover:bg-(--chrome-action-hover) hover:text-foreground'
      ),
      onClick: () => {
        haptic('tap')
        host.navigate(PATH)
      },
      children: [
        jsx(Codicon, { name: 'graph', size: '0.7rem' }),
        n == null ? null : jsx('span', { children: n })
      ]
    })
  })
}

export default {
  id: ID,
  name: 'Local Contributions',
  description: 'GitHub-style heatmap of git commits authored on this Omarchy machine.',
  defaultEnabled: true,
  register(ctx) {
    pluginCtx = ctx
    ctx.i18n.register({
      en: {
        nav: 'Garden',
        open: 'Open local contributions'
      }
    })

    ctx.register({
      id: 'page',
      area: ROUTES_AREA,
      title: 'Contributions',
      data: { path: PATH },
      render: () => jsx(GardenPage, {})
    })

    ctx.register({
      id: 'nav',
      area: SIDEBAR_NAV_AREA,
      order: 55,
      data: { path: PATH, label: 'Garden', codicon: 'graph' }
    })

    ctx.register({
      id: 'chip',
      area: 'statusBar.right',
      order: 125,
      render: () => jsx(TodayChip, {})
    })

    ctx.register({
      id: 'open',
      area: PALETTE_AREA,
      data: {
        id: 'local-contrib.open',
        label: 'Open local contributions',
        keywords: ['github', 'heatmap', 'garden', 'commits', 'contributions', 'git', 'omarchy'],
        run: () => host.navigate(PATH)
      }
    })
  }
}
