export function feedbackDraft(entry) {
  return {
    status: entry?.status || 'planned',
    rating: entry?.rating ?? null,
    liked: entry?.liked || '',
    disliked: entry?.disliked || '',
    comment: entry?.comment || '',
    mode: entry?.effective_source === 'manual' ? 'manual' : 'review',
    choices: Object.fromEntries(
      (entry?.effective_source === 'manual' ? entry.signals : []).map((s) => [s.tag.id, s.value]),
    ),
  }
}
export function feedbackBody(draft) {
  const manual = draft.mode === 'manual'
  return {
    status: draft.status,
    rating: draft.rating,
    liked: manual ? null : draft.liked.trim() || null,
    disliked: manual ? null : draft.disliked.trim() || null,
    comment: manual ? null : draft.comment.trim() || null,
    manual_tags: manual ? Object.entries(draft.choices).map(([tag_id, value]) => ({ tag_id, value })) : [],
  }
}
export function feedbackError(draft) {
  if (
    draft.mode === 'review' &&
    draft.liked.trim().length + draft.disliked.trim().length + draft.comment.trim().length > 5000
  )
    return 'Отзыв должен быть не длиннее 5000 символов'
  if (draft.mode === 'manual' && Object.keys(draft.choices).length > 100) return 'Можно отметить до 100 тегов'
  return null
}
