import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ChatPanel } from '../ChatPanel';
import type { ChatMessage } from '@/lib/types';

describe('ChatPanel', () => {
  it('renders user and assistant messages', () => {
    const msgs: ChatMessage[] = [
      { role: 'user', content: 'Buy 5 AAPL' },
      {
        role: 'assistant',
        content: 'Done.',
        actions: {
          trades: [
            {
              ticker: 'AAPL',
              side: 'buy',
              quantity: 5,
              price: 191.42,
              status: 'executed',
            },
          ],
        },
      },
    ];
    render(<ChatPanel messages={msgs} onSend={async () => {}} busy={false} />);
    expect(screen.getByTestId('chat-msg-user')).toHaveTextContent('Buy 5 AAPL');
    expect(screen.getByTestId('chat-msg-assistant')).toHaveTextContent('Done.');
    const action = screen.getByTestId('action-trade-0');
    expect(action.getAttribute('data-status')).toBe('executed');
    expect(action).toHaveTextContent(/buy/i);
    expect(action).toHaveTextContent('AAPL');
    expect(action).toHaveTextContent('191.42');
  });

  it('renders rejected trade with reason', () => {
    const msgs: ChatMessage[] = [
      {
        role: 'assistant',
        content: 'Sorry.',
        actions: {
          trades: [
            {
              ticker: 'TSLA',
              side: 'buy',
              quantity: 5,
              status: 'rejected',
              reason: 'insufficient_cash',
            },
          ],
        },
      },
    ];
    render(<ChatPanel messages={msgs} onSend={async () => {}} busy={false} />);
    const action = screen.getByTestId('action-trade-0');
    expect(action.getAttribute('data-status')).toBe('rejected');
    expect(action).toHaveTextContent('insufficient_cash');
  });

  it('renders watchlist actions both executed and rejected', () => {
    const msgs: ChatMessage[] = [
      {
        role: 'assistant',
        content: 'Updated watchlist.',
        actions: {
          watchlist_changes: [
            { ticker: 'PYPL', action: 'add', status: 'executed' },
            {
              ticker: 'ZZZZZ',
              action: 'add',
              status: 'rejected',
              reason: 'unknown_ticker',
            },
          ],
        },
      },
    ];
    render(<ChatPanel messages={msgs} onSend={async () => {}} busy={false} />);
    expect(screen.getByTestId('action-watchlist-0')).toHaveTextContent('PYPL');
    const rejected = screen.getByTestId('action-watchlist-1');
    expect(rejected.getAttribute('data-status')).toBe('rejected');
    expect(rejected).toHaveTextContent('unknown_ticker');
  });

  it('shows loading indicator when busy', () => {
    render(<ChatPanel messages={[]} onSend={async () => {}} busy={true} />);
    expect(screen.getByTestId('chat-loading')).toBeInTheDocument();
  });

  it('invokes onSend when the form is submitted', async () => {
    const onSend = vi.fn(async () => {});
    render(<ChatPanel messages={[]} onSend={onSend} busy={false} />);
    const user = userEvent.setup();
    await user.type(screen.getByLabelText('chat-input'), 'hello');
    await user.click(screen.getByRole('button', { name: /send/i }));
    expect(onSend).toHaveBeenCalledWith('hello');
  });
});
