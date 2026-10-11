import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';
import { CreatePortfolioModal } from '../src/components/portfolio/CreatePortfolioModal';
import { PortfolioHub } from '../src/components/portfolio/PortfolioHub';
import { PortfolioProvider, usePortfolio } from '../src/context/PortfolioContext';
import * as portfoliosApi from '../src/api/portfolios';
import * as analyticsApi from '../src/api/analytics';
import { PortfolioDetailResponse, PortfolioResponse } from '../src/types/portfolio';

vi.mock('../src/api/portfolios');
vi.mock('../src/api/analytics');

describe('Stage 1: Create Portfolio UI and Modal Tests', () => {
  const mockCreatedPortfolio: PortfolioDetailResponse = {
    id: 'port-new-999',
    name: 'Growth Tech Basket',
    description: 'High-growth technology focus',
    is_sample: false,
    created_at: '2026-10-11T12:00:00Z',
    updated_at: '2026-10-11T12:00:00Z',
    holdings_count: 0,
    holdings: [],
  };

  const TestConsumer: React.FC<{ isOpen: boolean; onClose: () => void; onCreated?: (name: string) => void }> = ({
    isOpen,
    onClose,
    onCreated,
  }) => {
    const { activePortfolioId, portfolios, isLoading } = usePortfolio();
    return (
      <div>
        <div data-testid="loading-state">{isLoading ? 'loading' : 'idle'}</div>
        <div data-testid="active-portfolio-indicator">{activePortfolioId || 'none'}</div>
        <div data-testid="portfolios-count">{portfolios.length}</div>
        <CreatePortfolioModal isOpen={isOpen} onClose={onClose} onCreated={onCreated} />
      </div>
    );
  };

  const renderWithProvider = async (ui: React.ReactElement) => {
    const res = render(<PortfolioProvider>{ui}</PortfolioProvider>);
    await waitFor(() => {
      expect(screen.getByTestId('loading-state')).toHaveTextContent('idle');
    });
    return res;
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(portfoliosApi.fetchPortfolios).mockResolvedValue([
      {
        id: 'port-demo-1',
        name: 'Demo Indian Bluechip Portfolio',
        description: 'Demo',
        is_sample: true,
        created_at: '2026-10-10T00:00:00Z',
        updated_at: '2026-10-10T00:00:00Z',
        holdings_count: 5,
      },
    ]);
  });

  describe('Modal Visibility & Basic Controls', () => {
    it('does not render when isOpen is false', async () => {
      await renderWithProvider(<TestConsumer isOpen={false} onClose={vi.fn()} />);
      expect(screen.queryByTestId('create-portfolio-modal')).not.toBeInTheDocument();
    });

    it('renders dialog with accessibility attributes when isOpen is true', async () => {
      await renderWithProvider(<TestConsumer isOpen={true} onClose={vi.fn()} />);

      const dialog = screen.getByRole('dialog');
      expect(dialog).toBeInTheDocument();
      expect(dialog).toHaveAttribute('aria-modal', 'true');
      expect(screen.getByText('Create New Portfolio')).toBeInTheDocument();
      expect(screen.getByLabelText(/portfolio name/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/description/i)).toBeInTheDocument();
    });

    it('calls onClose when clicking Cancel button', async () => {
      const handleClose = vi.fn();
      await renderWithProvider(<TestConsumer isOpen={true} onClose={handleClose} />);

      fireEvent.click(screen.getByTestId('cancel-create-portfolio-btn'));
      expect(handleClose).toHaveBeenCalledTimes(1);
    });

    it('calls onClose when clicking the modal close X button', async () => {
      const handleClose = vi.fn();
      await renderWithProvider(<TestConsumer isOpen={true} onClose={handleClose} />);

      fireEvent.click(screen.getByTestId('close-create-portfolio-modal'));
      expect(handleClose).toHaveBeenCalledTimes(1);
    });

    it('calls onClose when clicking the modal backdrop', async () => {
      const handleClose = vi.fn();
      await renderWithProvider(<TestConsumer isOpen={true} onClose={handleClose} />);

      fireEvent.click(screen.getByTestId('create-portfolio-modal-backdrop'));
      expect(handleClose).toHaveBeenCalledTimes(1);
    });
  });

  describe('Form Validation & Field Boundaries', () => {
    it('shows validation error when attempting to submit with empty name', async () => {
      await renderWithProvider(<TestConsumer isOpen={true} onClose={vi.fn()} />);

      fireEvent.click(screen.getByTestId('submit-create-portfolio-btn'));

      expect(screen.getByTestId('create-portfolio-error')).toHaveTextContent(
        'Portfolio name is required (1-100 characters).'
      );
      expect(portfoliosApi.createPortfolio).not.toHaveBeenCalled();
    });

    it('shows validation error when name contains only whitespace', async () => {
      await renderWithProvider(<TestConsumer isOpen={true} onClose={vi.fn()} />);

      const nameInput = screen.getByTestId('portfolio-name-input');
      fireEvent.change(nameInput, { target: { value: '     ' } });
      fireEvent.click(screen.getByTestId('submit-create-portfolio-btn'));

      expect(screen.getByTestId('create-portfolio-error')).toHaveTextContent(
        'Portfolio name is required (1-100 characters).'
      );
      expect(portfoliosApi.createPortfolio).not.toHaveBeenCalled();
    });

    it('updates character counters dynamically as user types', async () => {
      await renderWithProvider(<TestConsumer isOpen={true} onClose={vi.fn()} />);

      const nameInput = screen.getByTestId('portfolio-name-input');
      fireEvent.change(nameInput, { target: { value: 'Alpha Basket' } });
      expect(screen.getByText('12/100 characters')).toBeInTheDocument();

      const descInput = screen.getByTestId('portfolio-description-input');
      fireEvent.change(descInput, { target: { value: 'Medium risk allocation strategy' } });
      expect(screen.getByText('31/255 characters')).toBeInTheDocument();
    });
  });

  describe('Successful Portfolio Creation Flow', () => {
    it('creates portfolio, refreshes context, selects new portfolio ID, and triggers callbacks', async () => {
      const handleClose = vi.fn();
      const handleCreated = vi.fn();

      vi.mocked(portfoliosApi.createPortfolio).mockResolvedValueOnce(mockCreatedPortfolio);
      vi.mocked(portfoliosApi.fetchPortfolios).mockResolvedValueOnce([
        {
          id: 'port-demo-1',
          name: 'Demo Indian Bluechip Portfolio',
          description: 'Demo',
          is_sample: true,
          created_at: '2026-10-10T00:00:00Z',
          updated_at: '2026-10-10T00:00:00Z',
          holdings_count: 5,
        },
        {
          id: 'port-new-999',
          name: 'Growth Tech Basket',
          description: 'High-growth technology focus',
          is_sample: false,
          created_at: '2026-10-11T12:00:00Z',
          updated_at: '2026-10-11T12:00:00Z',
          holdings_count: 0,
        },
      ]);

      await renderWithProvider(
        <TestConsumer isOpen={true} onClose={handleClose} onCreated={handleCreated} />
      );

      const nameInput = screen.getByTestId('portfolio-name-input');
      const descInput = screen.getByTestId('portfolio-description-input');

      fireEvent.change(nameInput, { target: { value: '  Growth Tech Basket  ' } });
      fireEvent.change(descInput, { target: { value: '  High-growth technology focus  ' } });

      const submitBtn = screen.getByTestId('submit-create-portfolio-btn');
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(portfoliosApi.createPortfolio).toHaveBeenCalledWith({
          name: 'Growth Tech Basket',
          description: 'High-growth technology focus',
          is_sample: false,
        });
      });

      await waitFor(() => {
        expect(handleCreated).toHaveBeenCalledWith('Growth Tech Basket');
        expect(handleClose).toHaveBeenCalledTimes(1);
        expect(screen.getByTestId('active-portfolio-indicator')).toHaveTextContent('port-new-999');
      });
    });

    it('passes null for description when optional description is left blank', async () => {
      const handleClose = vi.fn();
      vi.mocked(portfoliosApi.createPortfolio).mockResolvedValueOnce(mockCreatedPortfolio);

      await renderWithProvider(<TestConsumer isOpen={true} onClose={handleClose} />);

      fireEvent.change(screen.getByTestId('portfolio-name-input'), {
        target: { value: 'Growth Tech Basket' },
      });

      fireEvent.click(screen.getByTestId('submit-create-portfolio-btn'));

      await waitFor(() => {
        expect(portfoliosApi.createPortfolio).toHaveBeenCalledWith({
          name: 'Growth Tech Basket',
          description: null,
          is_sample: false,
        });
      });
    });
  });

  describe('API Errors & Loading State', () => {
    it('displays backend error when server rejects with reserved name or validation error', async () => {
      const reservedError = {
        isAxiosError: true,
        name: 'AxiosError',
        message: "The name 'Demo Indian Bluechip Portfolio' is reserved for the canonical demo portfolio.",
        response: {
          status: 422,
          data: {
            success: false,
            error: {
              code: 'VALIDATION_ERROR',
              message: "The name 'Demo Indian Bluechip Portfolio' is reserved for the canonical demo portfolio.",
            },
          },
        },
      };

      vi.mocked(portfoliosApi.createPortfolio).mockRejectedValueOnce(reservedError);

      await renderWithProvider(<TestConsumer isOpen={true} onClose={vi.fn()} />);

      fireEvent.change(screen.getByTestId('portfolio-name-input'), {
        target: { value: 'Demo Indian Bluechip Portfolio' },
      });

      fireEvent.click(screen.getByTestId('submit-create-portfolio-btn'));

      await waitFor(() => {
        expect(screen.getByTestId('create-portfolio-error')).toHaveTextContent(
          "The name 'Demo Indian Bluechip Portfolio' is reserved for the canonical demo portfolio."
        );
      });

      // Confirm button is re-enabled for retry
      expect(screen.getByTestId('submit-create-portfolio-btn')).not.toBeDisabled();
    });

    it('displays fallback error message on generic unexpected failure', async () => {
      vi.mocked(portfoliosApi.createPortfolio).mockRejectedValueOnce(new Error('Network disconnected'));

      await renderWithProvider(<TestConsumer isOpen={true} onClose={vi.fn()} />);

      fireEvent.change(screen.getByTestId('portfolio-name-input'), {
        target: { value: 'Resilience Test Basket' },
      });

      fireEvent.click(screen.getByTestId('submit-create-portfolio-btn'));

      await waitFor(() => {
        expect(screen.getByTestId('create-portfolio-error')).toHaveTextContent(
          'Network disconnected'
        );
      });
    });
  });

  describe('PortfolioHub Integration Tests', () => {
    const mockBluechipPortfolio: PortfolioResponse = {
      id: 'demo-portfolio-1',
      name: 'Demo Indian Bluechip Portfolio',
      description: 'Canonical bluechip benchmark portfolio',
      is_sample: true,
      created_at: '2026-10-10T00:00:00Z',
      updated_at: '2026-10-10T00:00:00Z',
      holdings_count: 5,
    };

    beforeEach(() => {
      vi.mocked(analyticsApi.fetchPortfolioAnalytics).mockResolvedValue({
        portfolio_id: 'demo-portfolio-1',
        portfolio_name: 'Demo Indian Bluechip Portfolio',
        is_sample: true,
        calculated_at: '2026-10-10T00:00:00Z',
        status: 'COMPLETE',
        valuation: {
          total_cost_basis: 500000,
          total_market_value: 575000,
          priced_cost_basis: 500000,
          unrealized_pnl: 75000,
          unrealized_pnl_percent: 15.0,
        },
        completeness: {
          is_complete: true,
          completeness_ratio: 1.0,
          total_holdings_count: 5,
          priced_holdings_count: 5,
          unpriced_holdings_count: 0,
          has_stale_prices: false,
          has_simulated_prices: true,
          unpriced_positions: [],
        },
        concentration: {
          top_holding_symbol: 'RELIANCE',
          top_holding_weight_percent: 28.5,
          top_3_concentration_percent: 68.2,
          herfindahl_index: 0.22,
          effective_holdings_count: 4.5,
          concentration_tier: 'MODERATE',
        },
        sector_allocations: [],
        holdings: [],
        disclaimer: 'Educational purposes only.',
      });

      vi.mocked(analyticsApi.fetchPortfolioInsights).mockResolvedValue({
        portfolio_id: 'demo-portfolio-1',
        insights: [],
        total_insights: 0,
        generated_at: '2026-10-10T00:00:00Z',
        is_sample_portfolio: true,
        disclaimer: 'Deterministic observations only',
      });
    });

    it('opens create modal when clicking New Portfolio button in PortfolioHub toolbar', async () => {
      vi.mocked(portfoliosApi.fetchPortfolios).mockResolvedValue([mockBluechipPortfolio]);

      render(
        <PortfolioProvider>
          <PortfolioHub />
        </PortfolioProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('new-portfolio-btn')).toBeInTheDocument();
      });

      // Initially modal is not open
      expect(screen.queryByTestId('create-portfolio-modal')).not.toBeInTheDocument();

      // Click New Portfolio button
      fireEvent.click(screen.getByTestId('new-portfolio-btn'));

      // Modal is rendered
      expect(screen.getByTestId('create-portfolio-modal')).toBeInTheDocument();
    });

    it('opens create modal from empty state and shows success banner in PortfolioHub after creation', async () => {
      // 1. Initial empty portfolios list
      vi.mocked(portfoliosApi.fetchPortfolios).mockResolvedValueOnce([]);

      render(
        <PortfolioProvider>
          <PortfolioHub />
        </PortfolioProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('empty-create-portfolio-btn')).toBeInTheDocument();
      });

      // Click "Create Custom Portfolio" in empty state
      fireEvent.click(screen.getByTestId('empty-create-portfolio-btn'));
      expect(screen.getByTestId('create-portfolio-modal')).toBeInTheDocument();

      // Setup mock responses for creation
      vi.mocked(portfoliosApi.createPortfolio).mockResolvedValueOnce(mockCreatedPortfolio);
      vi.mocked(portfoliosApi.fetchPortfolios).mockResolvedValueOnce([
        {
          id: 'port-new-999',
          name: 'Growth Tech Basket',
          description: 'High-growth technology focus',
          is_sample: false,
          created_at: '2026-10-11T12:00:00Z',
          updated_at: '2026-10-11T12:00:00Z',
          holdings_count: 0,
        },
      ]);

      // Fill in and submit
      fireEvent.change(screen.getByTestId('portfolio-name-input'), {
        target: { value: 'Growth Tech Basket' },
      });
      fireEvent.click(screen.getByTestId('submit-create-portfolio-btn'));

      // Modal closes and success banner appears in PortfolioHub
      await waitFor(() => {
        expect(screen.queryByTestId('create-portfolio-modal')).not.toBeInTheDocument();
        expect(screen.getByTestId('portfolio-create-success-banner')).toBeInTheDocument();
        expect(
          screen.getByText('Portfolio "Growth Tech Basket" created successfully.')
        ).toBeInTheDocument();
      });

      // Can dismiss the success banner
      fireEvent.click(screen.getByLabelText(/dismiss success message/i));
      expect(screen.queryByTestId('portfolio-create-success-banner')).not.toBeInTheDocument();
    });
  });
});
