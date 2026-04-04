import type {
  ConversationMessage,
  ConversationSummary,
  CreateReviewRequest,
  CreateReviewResponse,
  ReviewHistoryItem,
  ReviewTask,
} from '../types/review'

const BACKEND_BASE_URL =
  import.meta.env.VITE_BACKEND_BASE_URL?.replace(/\/$/, '') ??
  'http://localhost:8080'

function buildApiUrl(path: string): string {
  return `${BACKEND_BASE_URL}${path}`
}

async function parseErrorMessage(
  response: Response,
  fallbackMessage: string
): Promise<string> {
  try {
    const text = await response.text()
    return text || fallbackMessage
  } catch {
    return fallbackMessage
  }
}

export async function createReviewTask(
  request: CreateReviewRequest
): Promise<CreateReviewResponse> {
  const response = await fetch(buildApiUrl('/api/reviews'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })

  if (!response.ok) {
    throw new Error(await parseErrorMessage(response, 'Failed to create review task'))
  }

  return (await response.json()) as CreateReviewResponse
}

export async function fetchReviewTask(taskId: string): Promise<ReviewTask> {
  const response = await fetch(
    buildApiUrl(`/api/reviews/${encodeURIComponent(taskId)}`)
  )

  if (!response.ok) {
    throw new Error(await parseErrorMessage(response, 'Failed to load review task'))
  }

  return (await response.json()) as ReviewTask
}

export async function fetchReviewHistory(limit = 50): Promise<ReviewHistoryItem[]> {
  const response = await fetch(
    buildApiUrl(`/api/reviews?limit=${encodeURIComponent(String(limit))}`)
  )

  if (!response.ok) {
    throw new Error(await parseErrorMessage(response, 'Failed to load review history'))
  }

  return (await response.json()) as ReviewHistoryItem[]
}

export async function fetchConversations(limit = 50): Promise<ConversationSummary[]> {
  const response = await fetch(
    buildApiUrl(`/api/reviews/conversations?limit=${encodeURIComponent(String(limit))}`)
  )
  if (!response.ok) {
    throw new Error(await parseErrorMessage(response, 'Failed to load conversations'))
  }
  return (await response.json()) as ConversationSummary[]
}

export async function fetchConversationMessages(
  conversationId: string,
  limit = 500
): Promise<ConversationMessage[]> {
  const response = await fetch(
    buildApiUrl(
      `/api/reviews/conversations/${encodeURIComponent(
        conversationId
      )}/messages?limit=${encodeURIComponent(String(limit))}`
    )
  )
  if (!response.ok) {
    throw new Error(await parseErrorMessage(response, 'Failed to load conversation messages'))
  }
  return (await response.json()) as ConversationMessage[]
}

export function createReviewEventSource(taskId: string): EventSource {
  return new EventSource(buildApiUrl(`/api/reviews/${encodeURIComponent(taskId)}/events`))
}
