import { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';

// Markdown component styles
const markdownComponents = {
  h1: ({ children, ...props }: any) => <h1 style={{ fontSize: '24px', fontWeight: 600, marginTop: '24px', marginBottom: '16px', color: '#111827' }} {...props}>{children}</h1>,
  h2: ({ children, ...props }: any) => <h2 style={{ fontSize: '20px', fontWeight: 600, marginTop: '20px', marginBottom: '12px', color: '#111827' }} {...props}>{children}</h2>,
  h3: ({ children, ...props }: any) => <h3 style={{ fontSize: '18px', fontWeight: 600, marginTop: '16px', marginBottom: '10px', color: '#111827' }} {...props}>{children}</h3>,
  p: ({ children, ...props }: any) => <p style={{ marginBottom: '12px' }} {...props}>{children}</p>,
  ul: ({ children, ...props }: any) => <ul style={{ marginBottom: '12px', paddingLeft: '24px' }} {...props}>{children}</ul>,
  ol: ({ children, ...props }: any) => <ol style={{ marginBottom: '12px', paddingLeft: '24px' }} {...props}>{children}</ol>,
  li: ({ children, ...props }: any) => <li style={{ marginBottom: '6px' }} {...props}>{children}</li>,
  strong: ({ children, ...props }: any) => <strong style={{ fontWeight: 600 }} {...props}>{children}</strong>,
  em: ({ children, ...props }: any) => <em style={{ fontStyle: 'italic' }} {...props}>{children}</em>,
};

// Markdown components for thinking area (smaller, lighter styling)
const thinkingMarkdownComponents = {
  h1: ({ children, ...props }: any) => <h1 style={{ fontSize: '14px', fontWeight: 600, marginTop: '8px', marginBottom: '4px', color: '#9ca3af' }} {...props}>{children}</h1>,
  h2: ({ children, ...props }: any) => <h2 style={{ fontSize: '13px', fontWeight: 600, marginTop: '6px', marginBottom: '4px', color: '#9ca3af' }} {...props}>{children}</h2>,
  h3: ({ children, ...props }: any) => <h3 style={{ fontSize: '12px', fontWeight: 600, marginTop: '6px', marginBottom: '4px', color: '#9ca3af' }} {...props}>{children}</h3>,
  p: ({ children, ...props }: any) => <p style={{ marginBottom: '4px', color: '#9ca3af' }} {...props}>{children}</p>,
  ul: ({ children, ...props }: any) => <ul style={{ marginBottom: '4px', paddingLeft: '20px', color: '#9ca3af' }} {...props}>{children}</ul>,
  ol: ({ children, ...props }: any) => <ol style={{ marginBottom: '4px', paddingLeft: '20px', color: '#9ca3af' }} {...props}>{children}</ol>,
  li: ({ children, ...props }: any) => <li style={{ marginBottom: '2px', color: '#9ca3af' }} {...props}>{children}</li>,
  strong: ({ children, ...props }: any) => <strong style={{ fontWeight: 600, color: '#9ca3af' }} {...props}>{children}</strong>,
  em: ({ children, ...props }: any) => <em style={{ fontStyle: 'italic', color: '#9ca3af' }} {...props}>{children}</em>,
  code: ({ children, ...props }: any) => <code style={{ backgroundColor: '#f3f4f6', padding: '2px 4px', borderRadius: '3px', fontSize: '12px', color: '#9ca3af' }} {...props}>{children}</code>,
  pre: ({ children, ...props }: any) => <pre style={{ backgroundColor: '#f3f4f6', padding: '8px', borderRadius: '4px', fontSize: '12px', color: '#9ca3af', overflow: 'auto' }} {...props}>{children}</pre>,
};

interface Draft {
  title: string;
  content: string;
  instructions: string;
}

interface Metadata {
  safety_score?: number;
  empathy_score?: number;
  clarity_score?: number;
  total_revisions: number;
}

interface ConversationItem {
  type: 'user' | 'assistant' | 'loading';
  content?: string;
  draft?: Draft;
  metadata?: Metadata;
  isStreaming?: boolean;
  agentThoughts?: string[];
  isEditing?: boolean;
  editedDraft?: Draft;
  originalUserMessage?: string; // Track the original user message that generated this draft
}

const AGENT_INFO: Record<string, { displayName: string }> = {
  intent_router: { displayName: 'Intent Router' },
  chat: { displayName: 'Chat Agent' },
  supervisor: { displayName: 'Supervisor' },
  drafter: { displayName: 'Drafter' },
  safety_guardian: { displayName: 'Safety Guardian' },
  clinical_critic: { displayName: 'Clinical Critic' },
};

function App() {
  const [message, setMessage] = useState('');
  const [threadId] = useState(`thread-${Date.now()}`);
  const [conversation, setConversation] = useState<ConversationItem[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [editedContent, setEditedContent] = useState<string>('');
  const [editedInstructions, setEditedInstructions] = useState<string>('');
  const [editedTitle, setEditedTitle] = useState<string>('');
  const [saving, setSaving] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [conversation]);

  const handleEditDraft = (index: number) => {
    const item = conversation[index];
    if (item.draft) {
      setEditingIndex(index);
      setEditedTitle(item.draft.title);
      setEditedInstructions(item.draft.instructions);
      setEditedContent(item.draft.content);
    }
  };

  const handleCancelEdit = () => {
    setEditingIndex(null);
    setEditedTitle('');
    setEditedInstructions('');
    setEditedContent('');
  };

  const handleSaveDraft = async (index: number) => {
    const item = conversation[index];
    if (!item.draft) return;

    setSaving(true);
    try {
      const editedDraft = {
        title: editedTitle,
        instructions: editedInstructions,
        content: editedContent,
      };

      // Save to backend
      const response = await fetch('http://localhost:8000/save-draft', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          thread_id: threadId,
          draft: editedDraft,
          original_message: item.originalUserMessage || '',
        }),
      });

      if (response.ok) {
        // Draft is now saved to SQLite via backend (no localStorage needed)

        // Update the conversation item with edited draft
        setConversation(prev => {
          const updated = [...prev];
          updated[index] = {
            ...updated[index],
            draft: editedDraft,
          };
          return updated;
        });
        setEditingIndex(null);
        setEditedTitle('');
        setEditedInstructions('');
        setEditedContent('');
      } else {
        alert('Failed to save draft');
      }
    } catch (error) {
      console.error('Error saving draft:', error);
      alert('Error saving draft');
    } finally {
      setSaving(false);
    }
  };


  const addStreamingThought = (thought: string) => {
    setConversation(prev => {
      // Remove loading indicator if present
      const withoutLoading = prev.filter(item => item.type !== 'loading');

      // Find the last assistant message that's streaming
      let foundIndex = -1;
      for (let i = withoutLoading.length - 1; i >= 0; i--) {
        if (withoutLoading[i].type === 'assistant' && withoutLoading[i].isStreaming) {
          foundIndex = i;
          break;
        }
      }

      if (foundIndex >= 0) {
        // Append new thought to existing streaming message
        const updated = [...withoutLoading];
        const existingThoughts = updated[foundIndex].agentThoughts || [];
        // Check if this exact thought was just added (avoid immediate duplicates)
        const lastThought = existingThoughts[existingThoughts.length - 1];
        if (lastThought !== thought) {
          updated[foundIndex] = {
            ...updated[foundIndex],
            agentThoughts: [...existingThoughts, thought],
          };
        }
        return updated;
      } else {
        // Add new streaming message placeholder with first thought
        return [...withoutLoading, {
          type: 'assistant',
          content: '',
          isStreaming: true,
          agentThoughts: [thought],
        }];
      }
    });
  };

  const extractAgentThoughts = (nodeName: string, nodeData: any): string[] => {
    const thoughts: string[] = [];

    if (!nodeData || typeof nodeData !== 'object') return thoughts;

    // Extract routing decisions from supervisor (show first)
    if (nodeData.next_worker && nodeName === 'supervisor') {
      const nextAgent = AGENT_INFO[nodeData.next_worker];
      let nextName: string;
      if (nextAgent) {
        nextName = nextAgent.displayName;
      } else {
        // Format node names like "human_review" to "Human Review"
        nextName = nodeData.next_worker
          .replace(/_/g, ' ')
          .replace(/\b\w/g, (l: string) => l.toUpperCase());
      }
      thoughts.push(`Routing to ${nextName}`);
    }

    // Extract intent routing (skip for chat route)
    if (nodeData.next_worker && nodeName === 'intent_router') {
      if (nodeData.next_worker !== 'chat') {
        thoughts.push(`Intent: CBT exercise creation`);
      }
      // Don't add anything for chat route - no thinking text needed
    }

    // Extract draft creation info (for drafter)
    if (nodeData.current_draft && nodeName === 'drafter') {
      const draft = nodeData.current_draft;
      const draftHistory = nodeData.draft_history || [];
      const versionNum = draftHistory.length > 0 ? draftHistory[draftHistory.length - 1].version_number : 1;
      thoughts.push(`Draft created: "${draft.title || 'New draft'}" (v${versionNum})`);
    }

    // Extract critiques with full content for review agents (safety_guardian, clinical_critic)
    if (nodeData.critiques && Array.isArray(nodeData.critiques)) {
      const recentCritiques = nodeData.critiques.slice(-1);
      recentCritiques.forEach((critique: any) => {
        if (critique.content && critique.author) {
          if (nodeName === 'safety_guardian' || nodeName === 'clinical_critic') {
            const status = critique.approved ? 'Approved' : 'Rejected';
            // Include full critique content
            thoughts.push(`${critique.author}: ${status}\n${critique.content}`);
          }
        }
      });
    }

    // Extract metadata scores - show scores that were updated at this step
    if (nodeData.metadata) {
      const meta = nodeData.metadata;
      const scoreParts: string[] = [];

      // Only show scores that are not null/undefined
      if (meta.safety_score !== null && meta.safety_score !== undefined) {
        scoreParts.push(`Safety: ${meta.safety_score.toFixed(1)}`);
      }
      if (meta.empathy_score !== null && meta.empathy_score !== undefined) {
        scoreParts.push(`Empathy: ${meta.empathy_score.toFixed(1)}`);
      }
      if (meta.clarity_score !== null && meta.clarity_score !== undefined) {
        scoreParts.push(`Clarity: ${meta.clarity_score.toFixed(1)}`);
      }

      if (scoreParts.length > 0) {
        thoughts.push(`Scores: ${scoreParts.join(', ')}`);
      }
    }

    return thoughts;
  };

  const handleSendMessage = async () => {
    if (!message.trim() || isProcessing) return;

    const userMessage = message;
    setConversation(prev => [...prev, { type: 'user', content: userMessage }]);

    // Memory agent will handle retrieval - just proceed with workflow
    // Add loading indicator
    setConversation(prev => [...prev, { type: 'loading' }]);
    setMessage('');
    setIsProcessing(true);

    try {
      const response = await fetch('http://localhost:8000/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMessage, thread_id: threadId })
      });

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      if (!reader) return;

      let assistantMessageAdded = false;
      let isChatRoute = false;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));

              // Detect if this is a chat route
              if (data.intent_router && data.intent_router.next_worker === 'chat') {
                isChatRoute = true;
              }

              // Handle completion event - fetch final state for drafts or messages
              if (data.type === 'complete') {
                const stateResponse = await fetch(`http://localhost:8000/state/${threadId}`);
                const state = await stateResponse.json();

                // Check if memory agent retrieved a draft (check both memory_result and current_draft)
                const memoryResult = state.memory_result as any;
                if ((memoryResult && memoryResult.found && memoryResult.intent === 'retrieve') ||
                  (state.current_draft && memoryResult && memoryResult.intent === 'retrieve')) {
                  const draftToUse = state.current_draft || memoryResult?.draft;
                  const metadataToUse = state.metadata || memoryResult?.metadata || { total_revisions: 0 };
                  const originalMsg = memoryResult?.original_message || userMessage;

                  setConversation(prev => {
                    const withoutLoading = prev.filter(item => item.type !== 'loading');
                    return [...withoutLoading, {
                      type: 'assistant',
                      draft: draftToUse,
                      metadata: metadataToUse as Metadata,
                      originalUserMessage: originalMsg,
                      agentThoughts: [], // No thoughts for retrieved drafts
                    }];
                  });
                  setIsProcessing(false);
                  return;
                }

                // Keep thoughts and add final message
                if (!assistantMessageAdded) {
                  setConversation(prev => {
                    // Remove loading indicator
                    const withoutLoading = prev.filter(item => item.type !== 'loading');
                    const updated = [...withoutLoading];
                    const lastIndex = updated.length - 1;
                    const hasStreaming = updated[lastIndex]?.isStreaming;
                    const existingThoughts = hasStreaming ? updated[lastIndex].agentThoughts : undefined;

                    if (hasStreaming) {
                      updated.pop();
                    }

                    if (state.current_draft) {
                      // Use the draft from state (edited drafts are stored in SQLite via backend)
                      const draftToUse = state.current_draft;

                      updated.push({
                        type: 'assistant',
                        content: 'CBT Exercise Created',
                        draft: draftToUse,
                        metadata: state.metadata,
                        agentThoughts: existingThoughts,
                        originalUserMessage: userMessage, // Store original message for future edits
                      });
                    } else if (state.messages && state.messages.length > 0) {
                      // Find the last AI/assistant message
                      let lastAIMessage = null;
                      for (let i = state.messages.length - 1; i >= 0; i--) {
                        const msg = state.messages[i];
                        const msgType = msg.type || '';
                        if (msgType === 'ai' || msgType === 'AIMessage' ||
                          (msgType !== 'human' && msgType !== 'user' && msgType !== 'HumanMessage')) {
                          lastAIMessage = msg;
                          break;
                        }
                      }

                      if (!lastAIMessage && state.messages.length > 0) {
                        lastAIMessage = state.messages[state.messages.length - 1];
                      }

                      if (lastAIMessage) {
                        const messageContent = typeof lastAIMessage === 'string'
                          ? lastAIMessage
                          : (lastAIMessage.content || String(lastAIMessage));

                        if (messageContent && messageContent.trim()) {
                          updated.push({
                            type: 'assistant',
                            content: messageContent.trim(),
                            agentThoughts: existingThoughts,
                          });
                        }
                      }
                    }
                    return updated;
                  });
                  assistantMessageAdded = true;
                }
                break;
              }

              // Handle error events
              if (data.type === 'error') {
                setConversation(prev => [...prev, {
                  type: 'assistant',
                  content: `Error: ${data.error || 'Unknown error occurred'}`
                }]);
                break;
              }

              // Process stream events from graph nodes
              // Events have structure: { "node_name": { state_updates } }
              for (const [nodeName, nodeData] of Object.entries(data)) {
                if (nodeName === 'type') continue; // Skip metadata

                // Handle memory_agent retrieval result
                if (nodeName === 'memory_agent' && nodeData && typeof nodeData === 'object') {
                  const memoryResult = (nodeData as any).memory_result;
                  if (memoryResult && memoryResult.intent === 'retrieve' && memoryResult.found) {
                    // Memory agent found a draft - it will be handled in completion event
                    // Just skip adding thoughts for memory agent
                    continue;
                  }
                }

                // Add agent thoughts incrementally as they stream (skip for chat route)
                if (nodeName && nodeData && typeof nodeData === 'object' && !isChatRoute) {
                  const thoughts = extractAgentThoughts(nodeName, nodeData);
                  // Add each thought individually as it streams
                  thoughts.forEach(thought => {
                    if (!assistantMessageAdded) {
                      addStreamingThought(thought);
                    }
                  });
                }

                // Check if this is the chat node with messages
                if (nodeName === 'chat' && nodeData && typeof nodeData === 'object') {
                  const chatData = nodeData as any;
                  if (chatData.messages && Array.isArray(chatData.messages) && chatData.messages.length > 0) {
                    // Find the last AI message
                    const lastMessage = chatData.messages[chatData.messages.length - 1];
                    let messageContent = '';

                    // Extract content from serialized message object
                    if (typeof lastMessage === 'string') {
                      messageContent = lastMessage;
                    } else if (lastMessage && typeof lastMessage === 'object') {
                      // Handle properly serialized message objects
                      messageContent = lastMessage.content ||
                        (lastMessage.id && Array.isArray(lastMessage.id) ? lastMessage.id[2] : '') ||
                        String(lastMessage);
                      // Ensure it's a string
                      messageContent = typeof messageContent === 'string'
                        ? messageContent
                        : String(messageContent);
                    } else {
                      messageContent = String(lastMessage);
                    }

                    if (messageContent && messageContent.trim() && !assistantMessageAdded) {
                      // Keep thoughts and add final message after them
                      setConversation(prev => {
                        // Remove loading indicator
                        const withoutLoading = prev.filter(item => item.type !== 'loading');
                        const updated = [...withoutLoading];
                        const lastIndex = updated.length - 1;
                        if (updated[lastIndex]?.isStreaming) {
                          // Mark streaming as complete but keep thoughts
                          updated[lastIndex] = {
                            ...updated[lastIndex],
                            isStreaming: false,
                            content: messageContent.trim(),
                          };
                        } else {
                          updated.push({
                            type: 'assistant',
                            content: messageContent.trim(),
                          });
                        }
                        return updated;
                      });
                      assistantMessageAdded = true;
                    }
                  }
                }
              }
            } catch (e) {
              console.error('Error parsing stream data:', e);
            }
          }
        }
      }
    } catch (error) {
      setConversation(prev => {
        // Remove loading indicator
        const withoutLoading = prev.filter(item => item.type !== 'loading');
        const updated = [...withoutLoading];
        const lastIndex = updated.length - 1;
        const hasStreaming = updated[lastIndex]?.isStreaming;
        const existingThoughts = hasStreaming ? updated[lastIndex].agentThoughts : undefined;

        if (hasStreaming) {
          updated.pop();
        }
        updated.push({
          type: 'assistant',
          content: 'Error processing request',
          agentThoughts: existingThoughts,
        });
        return updated;
      });
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', fontFamily: 'system-ui, sans-serif' }}>
      {/* Header */}
      <div style={{ padding: '16px 24px', borderBottom: '1px solid #e5e7eb', backgroundColor: 'white' }}>
        <h1
          onClick={() => window.location.reload()}
          style={{ fontSize: '20px', margin: 0, color: '#1f2937', cursor: 'pointer', userSelect: 'none' }}
        >
          Clarity CBT
        </h1>
      </div>

      {/* Chat Area */}
      <div style={{ flex: 1, overflowY: 'auto', backgroundColor: 'white' }}>
        <div style={{ maxWidth: '800px', margin: '0 auto', padding: '32px 24px' }}>
          {conversation.length === 0 && (
            <div style={{ textAlign: 'center', paddingTop: '80px' }}>
              <h2 style={{ fontSize: '36px', fontWeight: 300, color: '#1f2937', marginBottom: '16px' }}>Hello</h2>
              <p style={{ color: '#6b7280' }}>How can I help you create a CBT exercise today?</p>
            </div>
          )}

          {conversation.map((item, idx) => {
            // Find the index of the last draft in the conversation
            let lastDraftIndex = -1;
            for (let i = conversation.length - 1; i >= 0; i--) {
              if (conversation[i].draft) {
                lastDraftIndex = i;
                break;
              }
            }
            const isLatestDraft = idx === lastDraftIndex && item.draft;

            return (
              <div key={idx} style={{ marginBottom: '32px' }}>
                {item.type === 'user' ? (
                  <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                    <div style={{ backgroundColor: '#f3f4f6', borderRadius: '9999px', padding: '12px 20px', maxWidth: '600px' }}>
                      <p style={{ margin: 0, color: '#1f2937' }}>{item.content}</p>
                    </div>
                  </div>
                ) : item.type === 'loading' ? (
                  <div style={{ display: 'flex', justifyContent: 'flex-start' }}>
                    <div style={{ backgroundColor: '#f3f4f6', borderRadius: '9999px', padding: '12px 20px', maxWidth: '600px', display: 'flex', gap: '4px', alignItems: 'center' }}>
                      {[0, 1, 2].map((index) => (
                        <span
                          key={index}
                          style={{
                            color: '#6b7280',
                            fontSize: '16px',
                            animation: `jumpDot 1.4s infinite`,
                            animationDelay: `${index * 0.2}s`,
                            display: 'inline-block',
                          }}
                        >
                          .
                        </span>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div>
                    {/* Show agent thoughts if present */}
                    {item.agentThoughts && item.agentThoughts.length > 0 && (
                      <div style={{
                        marginBottom: item.content || item.draft ? '16px' : '0',
                        paddingBottom: item.content || item.draft ? '16px' : '0',
                        borderBottom: item.content || item.draft ? '1px solid #e5e7eb' : 'none',
                      }}>
                        {item.agentThoughts.map((thought, thoughtIdx) => (
                          <div
                            key={thoughtIdx}
                            style={{
                              color: '#9ca3af',
                              fontSize: '13px',
                              lineHeight: '1.6',
                              marginBottom: '6px',
                              fontStyle: 'italic',
                              animation: thoughtIdx === item.agentThoughts!.length - 1 && item.isStreaming
                                ? 'fadeIn 0.3s ease-in'
                                : 'none',
                            }}
                          >
                            <ReactMarkdown components={thinkingMarkdownComponents}>
                              {thought}
                            </ReactMarkdown>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Show final message or draft */}
                    {item.draft ? (() => {
                      const displayDraft = item.draft;
                      return (
                        <div>
                          <div style={{ marginBottom: '12px' }}>
                            {editingIndex === idx ? (
                              <input
                                type="text"
                                value={editedTitle}
                                onChange={(e) => setEditedTitle(e.target.value)}
                                style={{
                                  fontSize: '20px',
                                  fontWeight: 400,
                                  color: '#111827',
                                  border: '1px solid #d1d5db',
                                  borderRadius: '6px',
                                  padding: '8px 12px',
                                  width: '100%',
                                }}
                              />
                            ) : (
                              <h2 style={{ fontSize: '20px', fontWeight: 400, color: '#111827', margin: 0 }}>
                                {displayDraft.title}
                              </h2>
                            )}
                          </div>

                          {item.metadata && (
                            <div style={{ display: 'flex', gap: '12px', fontSize: '12px', color: '#6b7280', marginBottom: '16px' }}>
                              <span>Safety {item.metadata.safety_score?.toFixed(1)}</span>
                              <span>Empathy {item.metadata.empathy_score?.toFixed(1)}</span>
                              <span>Clarity {item.metadata.clarity_score?.toFixed(1)}</span>
                              <span>{item.metadata.total_revisions} revisions</span>
                            </div>
                          )}

                          {editingIndex === idx ? (
                            <div>
                              <div style={{ marginBottom: '16px' }}>
                                <label style={{ display: 'block', fontSize: '13px', fontWeight: 500, color: '#374151', marginBottom: '6px' }}>
                                  Instructions
                                </label>
                                <textarea
                                  value={editedInstructions}
                                  onChange={(e) => setEditedInstructions(e.target.value)}
                                  style={{
                                    width: '100%',
                                    minHeight: '100px',
                                    padding: '12px',
                                    border: '1px solid #d1d5db',
                                    borderRadius: '6px',
                                    fontSize: '15px',
                                    fontFamily: 'inherit',
                                    lineHeight: '1.6',
                                    resize: 'vertical',
                                  }}
                                />
                              </div>
                              <div>
                                <label style={{ display: 'block', fontSize: '13px', fontWeight: 500, color: '#374151', marginBottom: '6px' }}>
                                  Content
                                </label>
                                <textarea
                                  value={editedContent}
                                  onChange={(e) => setEditedContent(e.target.value)}
                                  style={{
                                    width: '100%',
                                    minHeight: '300px',
                                    padding: '12px',
                                    border: '1px solid #d1d5db',
                                    borderRadius: '6px',
                                    fontSize: '15px',
                                    fontFamily: 'inherit',
                                    lineHeight: '1.6',
                                    resize: 'vertical',
                                  }}
                                />
                              </div>
                            </div>
                          ) : (
                            <>
                              <div style={{ color: '#374151', fontSize: '15px', lineHeight: '1.7', marginBottom: '16px' }}>
                                <ReactMarkdown components={markdownComponents}>
                                  {displayDraft.instructions}
                                </ReactMarkdown>
                              </div>

                              <div style={{ color: '#374151', fontSize: '15px', lineHeight: '1.7', marginBottom: '16px' }}>
                                <ReactMarkdown components={markdownComponents}>
                                  {displayDraft.content}
                                </ReactMarkdown>
                              </div>

                              {isLatestDraft && (
                                <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '16px' }}>
                                  <button
                                    onClick={() => handleEditDraft(idx)}
                                    style={{
                                      padding: '6px 16px',
                                      backgroundColor: '#f3f4f6',
                                      color: '#374151',
                                      border: 'none',
                                      borderRadius: '6px',
                                      cursor: 'pointer',
                                      fontSize: '14px',
                                      fontWeight: 500,
                                    }}
                                  >
                                    Edit
                                  </button>
                                </div>
                              )}
                            </>
                          )}

                          {editingIndex === idx && (
                            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '16px' }}>
                              <button
                                onClick={() => handleSaveDraft(idx)}
                                disabled={saving}
                                style={{
                                  padding: '6px 16px',
                                  backgroundColor: '#10b981',
                                  color: 'white',
                                  border: 'none',
                                  borderRadius: '6px',
                                  cursor: saving ? 'not-allowed' : 'pointer',
                                  fontSize: '14px',
                                  fontWeight: 500,
                                  opacity: saving ? 0.6 : 1,
                                }}
                              >
                                {saving ? 'Saving...' : 'Save'}
                              </button>
                              <button
                                onClick={handleCancelEdit}
                                disabled={saving}
                                style={{
                                  padding: '6px 16px',
                                  backgroundColor: '#f3f4f6',
                                  color: '#374151',
                                  border: 'none',
                                  borderRadius: '6px',
                                  cursor: saving ? 'not-allowed' : 'pointer',
                                  fontSize: '14px',
                                  fontWeight: 500,
                                }}
                              >
                                Cancel
                              </button>
                            </div>
                          )}
                        </div>
                      );
                    })() : (
                      <div style={{ color: '#374151', fontSize: '15px', lineHeight: '1.7' }}>
                        <ReactMarkdown components={markdownComponents}>
                          {item.content}
                        </ReactMarkdown>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}

          <div ref={chatEndRef} />
        </div>
      </div>

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(-2px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes jumpDot {
          0%, 100% {
            transform: translateY(0);
          }
          50% {
            transform: translateY(-8px);
          }
        }
      `}</style>

      {/* Input Area */}
      <div style={{ borderTop: '1px solid #e5e7eb', backgroundColor: 'white', padding: '24px' }}>
        <div style={{ maxWidth: '800px', margin: '0 auto', display: 'flex', gap: '12px', backgroundColor: '#f3f4f6', borderRadius: '24px', padding: '12px 24px', alignItems: 'center' }}>
          <input
            type="text"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSendMessage()}
            placeholder="Ask Clarity CBT"
            disabled={isProcessing}
            style={{ flex: 1, border: 'none', backgroundColor: 'transparent', outline: 'none', fontSize: '15px', color: '#1f2937' }}
          />
          <button
            onClick={handleSendMessage}
            disabled={isProcessing || !message.trim()}
            style={{ border: 'none', background: 'none', cursor: 'pointer', color: '#6b7280', fontSize: '24px', padding: 0 }}
          >
            ➤
          </button>
        </div>
        <p style={{ textAlign: 'center', fontSize: '12px', color: '#9ca3af', marginTop: '12px' }}>
          Clarity CBT uses AI agents. Verify important information.
        </p>
      </div>
    </div>
  );
}

export default App;

