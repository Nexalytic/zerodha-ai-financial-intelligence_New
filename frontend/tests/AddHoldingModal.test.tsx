import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { AddHoldingModal } from '../src/components/portfolio/AddHoldingModal';
import { PortfolioHub } from '../src/components/portfolio/PortfolioHub';
import { PortfolioProvider } from '../src/context/PortfolioContext';
import * as portfoliosApi from '../src/api/portfolios';
import * as analyticsApi from '../src/api/analytics';
import { HoldingResponse, PortfolioResponse } from '../src/types/portfolio';
import { PortfolioAnalyticsResponse } from '../src/types/analytics';

vi.mock('../src/api/portfolios');
vi.mock('../src/api/analytics');
vi.mock('../src/api/aiReasoning');

describe('Stage 2: Add Holding UI and Modal Tests', () => {
  const mockHoldingResponse: HoldingResponse = {
    id: 'h-new-123',
    portfolio_id: 'port-demo-1',
    symbol: 'INFY',
    exchange: 'NSE',
    quantity: 50,
    average_buy_price: 1520.25,
    sector: 'IT',
    asset_class: 'EQUITY',
    created_at: '2026-10-11T12:00:00Z',
    updated_at: '2026-10-11T12:00:00Z',
  };

  const mockPortfolio: PortfolioResponse = {
    id: 'port-demo-1',
    name: 'Growth Tech Basket',
    description: 'High-growth technology focus',
    is_sample: false,
    created_at: '2026-10-10T00:00:00Z',
    updated_at: '2026-10-10T00:00:00Z',
    holdings_count: 0,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(portfoliosApi.fetchPortfolios).mockResolvedValue([mockPortfolio]);
  });

  describe('Modal Visibility & Basic Controls', () => {
    it('does not render when isOpen is false', () => {
      render(
        <AddHoldingModal
          isOpen={false}
          onClose={vi.fn()}
          portfolioId="port-demo-1"
          portfolioName="Growth Tech Basket"
        />
      );

      expect(screen.queryByTestId('add-holding-modal')).not.toBeInTheDocument();
    });

    it('renders accessible dialog with portfolio name when isOpen is true', () => {
      render(
        <AddHoldingModal
          isOpen={true}
          onClose={vi.fn()}
          portfolioId="port-demo-1"
          portfolioName="Growth Tech Basket"
        />
      );

      const dialog = screen.getByRole('dialog');
      expect(dialog).toBeInTheDocument();
      expect(dialog).toHaveAttribute('aria-modal', 'true');
      expect(screen.getByText('Add Position to Portfolio')).toBeInTheDocument();
      expect(screen.getByText('Growth Tech Basket')).toBeInTheDocument();
      expect(screen.getByLabelText(/stock symbol/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/exchange/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/quantity/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/avg buy price/i)).toBeInTheDocument();
    });

    it('calls onClose when clicking Cancel button', () => {
      const handleClose = vi.fn();
      render(
        <AddHoldingModal
          isOpen={true}
          onClose={handleClose}
          portfolioId="port-demo-1"
          portfolioName="Growth Tech Basket"
        />
      );

      fireEvent.click(screen.getByTestId('cancel-add-holding-btn'));
      expect(handleClose).toHaveBeenCalledTimes(1);
    });

    it('calls onClose when clicking close X button', () => {
      const handleClose = vi.fn();
      render(
        <AddHoldingModal
          isOpen={true}
          onClose={handleClose}
          portfolioId="port-demo-1"
          portfolioName="Growth Tech Basket"
        />
      );

      fireEvent.click(screen.getByTestId('close-add-holding-modal'));
      expect(handleClose).toHaveBeenCalledTimes(1);
    });

    it('calls onClose when clicking backdrop overlay', () => {
      const handleClose = vi.fn();
      render(
        <AddHoldingModal
          isOpen={true}
          onClose={handleClose}
          portfolioId="port-demo-1"
          portfolioName="Growth Tech Basket"
        />
      );

      fireEvent.click(screen.getByTestId('add-holding-modal-backdrop'));
      expect(handleClose).toHaveBeenCalledTimes(1);
    });
  });

  describe('Form Defaults & Input Interactions', () => {
    it('initializes with default exchange NSE and asset class EQUITY', () => {
      render(
        <AddHoldingModal
          isOpen={true}
          onClose={vi.fn()}
          portfolioId="port-demo-1"
          portfolioName="Growth Tech Basket"
        />
      );

      expect(screen.getByTestId('holding-exchange-select')).toHaveValue('NSE');
      expect(screen.getByTestId('holding-asset-class-select')).toHaveValue('EQUITY');
      expect(screen.getByTestId('holding-symbol-input')).toHaveValue('');
      expect(screen.getByTestId('holding-quantity-input')).toHaveValue(null);
      expect(screen.getByTestId('holding-price-input')).toHaveValue(null);
    });

    it('automatically capitalizes stock symbol input', () => {
      render(
        <AddHoldingModal
          isOpen={true}
          onClose={vi.fn()}
          portfolioId="port-demo-1"
          portfolioName="Growth Tech Basket"
        />
      );

      const symbolInput = screen.getByTestId('holding-symbol-input');
      fireEvent.change(symbolInput, { target: { value: 'infy' } });
      expect(symbolInput).toHaveValue('INFY');
    });
  });

  describe('Client-Side Validation', () => {
    it('rejects submission with empty symbol', () => {
      render(
        <AddHoldingModal
          isOpen={true}
          onClose={vi.fn()}
          portfolioId="port-demo-1"
          portfolioName="Growth Tech Basket"
        />
      );

      fireEvent.click(screen.getByTestId('submit-add-holding-btn'));
      expect(screen.getByTestId('add-holding-error')).toHaveTextContent(
        'Stock symbol is required (1-20 characters).'
      );
      expect(portfoliosApi.addHolding).not.toHaveBeenCalled();
    });

    it('rejects invalid or special character symbols', () => {
      render(
        <AddHoldingModal
          isOpen={true}
          onClose={vi.fn()}
          portfolioId="port-demo-1"
          portfolioName="Growth Tech Basket"
        />
      );

      fireEvent.change(screen.getByTestId('holding-symbol-input'), {
        target: { value: 'BAD<SYMBOL>' },
      });
      fireEvent.click(screen.getByTestId('submit-add-holding-btn'));

      expect(screen.getByTestId('add-holding-error')).toHaveTextContent(
        'Symbol must be 1-20 alphanumeric characters, &, or -'
      );
      expect(portfoliosApi.addHolding).not.toHaveBeenCalled();
    });

    it('rejects non-positive or fractional quantity', () => {
      render(
        <AddHoldingModal
          isOpen={true}
          onClose={vi.fn()}
          portfolioId="port-demo-1"
          portfolioName="Growth Tech Basket"
        />
      );

      fireEvent.change(screen.getByTestId('holding-symbol-input'), {
        target: { value: 'TCS' },
      });
      fireEvent.change(screen.getByTestId('holding-quantity-input'), {
        target: { value: '0' },
      });
      fireEvent.click(screen.getByTestId('submit-add-holding-btn'));

      expect(screen.getByTestId('add-holding-error')).toHaveTextContent(
        'Quantity must be a positive whole number greater than 0.'
      );
      expect(portfoliosApi.addHolding).not.toHaveBeenCalled();
    });

    it('rejects non-positive average buy price', () => {
      render(
        <AddHoldingModal
          isOpen={true}
          onClose={vi.fn()}
          portfolioId="port-demo-1"
          portfolioName="Growth Tech Basket"
        />
      );

      fireEvent.change(screen.getByTestId('holding-symbol-input'), {
        target: { value: 'TCS' },
      });
      fireEvent.change(screen.getByTestId('holding-quantity-input'), {
        target: { value: '10' },
      });
      fireEvent.change(screen.getByTestId('holding-price-input'), {
        target: { value: '-50' },
      });
      fireEvent.click(screen.getByTestId('submit-add-holding-btn'));

      expect(screen.getByTestId('add-holding-error')).toHaveTextContent(
        'Average buy price must be a positive monetary amount greater than 0.'
      );
      expect(portfoliosApi.addHolding).not.toHaveBeenCalled();
    });
  });

  describe('Successful Holding Submission Flow', () => {
    it('submits holding with parsed types, closes modal, and triggers callback', async () => {
      const handleClose = vi.fn();
      const handleHoldingAdded = vi.fn();

      vi.mocked(portfoliosApi.addHolding).mockResolvedValueOnce(mockHoldingResponse);

      render(
        <AddHoldingModal
          isOpen={true}
          onClose={handleClose}
          portfolioId="port-demo-1"
          portfolioName="Growth Tech Basket"
          onHoldingAdded={handleHoldingAdded}
        />
      );

      fireEvent.change(screen.getByTestId('holding-symbol-input'), {
        target: { value: 'INFY' },
      });
      fireEvent.change(screen.getByTestId('holding-exchange-select'), {
        target: { value: 'NSE' },
      });
      fireEvent.change(screen.getByTestId('holding-quantity-input'), {
        target: { value: '50' },
      });
      fireEvent.change(screen.getByTestId('holding-price-input'), {
        target: { value: '1520.25' },
      });
      fireEvent.change(screen.getByTestId('holding-sector-input'), {
        target: { value: 'IT' },
      });
      fireEvent.change(screen.getByTestId('holding-asset-class-select'), {
        target: { value: 'EQUITY' },
      });

      fireEvent.click(screen.getByTestId('submit-add-holding-btn'));

      await waitFor(() => {
        expect(portfoliosApi.addHolding).toHaveBeenCalledWith('port-demo-1', {
          symbol: 'INFY',
          exchange: 'NSE',
          quantity: 50,
          average_buy_price: 1520.25,
          sector: 'IT',
          asset_class: 'EQUITY',
        });
      });

      await waitFor(() => {
        expect(handleHoldingAdded).toHaveBeenCalledWith('INFY', 50);
        expect(handleClose).toHaveBeenCalledTimes(1);
      });
    });
  });

  describe('API Errors & Server Feedback', () => {
    it('displays server validation error message on 422 response', async () => {
      const serverError = {
        isAxiosError: true,
        name: 'AxiosError',
        message: 'Average buy price must be strictly greater than 0',
        response: {
          status: 422,
          data: {
            success: false,
            error: {
              code: 'VALIDATION_ERROR',
              message: 'Average buy price must be strictly greater than 0',
            },
          },
        },
      };

      vi.mocked(portfoliosApi.addHolding).mockRejectedValueOnce(serverError);

      render(
        <AddHoldingModal
          isOpen={true}
          onClose={vi.fn()}
          portfolioId="port-demo-1"
          portfolioName="Growth Tech Basket"
        />
      );

      fireEvent.change(screen.getByTestId('holding-symbol-input'), {
        target: { value: 'INFY' },
      });
      fireEvent.change(screen.getByTestId('holding-quantity-input'), {
        target: { value: '10' },
      });
      fireEvent.change(screen.getByTestId('holding-price-input'), {
        target: { value: '100' },
      });

      fireEvent.click(screen.getByTestId('submit-add-holding-btn'));

      await waitFor(() => {
        expect(screen.getByTestId('add-holding-error')).toHaveTextContent(
          'Average buy price must be strictly greater than 0'
        );
      });

      // Submit button is re-enabled for user to fix inputs
      expect(screen.getByTestId('submit-add-holding-btn')).not.toBeDisabled();
    });
  });

  describe('PortfolioHub Integration Tests', () => {
    const mockEmptyAnalytics: PortfolioAnalyticsResponse = {
      portfolio_id: 'port-demo-1',
      portfolio_name: 'Growth Tech Basket',
      is_sample: false,
      calculated_at: '2026-10-11T12:00:00Z',
      status: 'COMPLETE',
      valuation: {
        total_cost_basis: 0,
        total_market_value: 0,
        priced_cost_basis: 0,
        unrealized_pnl: 0,
        unrealized_pnl_percent: 0,
      },
      completeness: {
        is_complete: true,
        completeness_ratio: 1.0,
        total_holdings_count: 0,
        priced_holdings_count: 0,
        unpriced_holdings_count: 0,
        has_stale_prices: false,
        has_simulated_prices: false,
        unpriced_positions: [],
      },
      concentration: {
        top_holding_symbol: null,
        top_holding_weight_percent: null,
        top_3_concentration_percent: 0,
        herfindahl_index: 0,
        effective_holdings_count: 0,
        concentration_tier: 'LOW',
      },
      sector_allocations: [],
      holdings: [],
      disclaimer: 'Educational purposes only.',
    };

    const mockUpdatedAnalytics: PortfolioAnalyticsResponse = {
      ...mockEmptyAnalytics,
      valuation: {
        total_cost_basis: 76012.5,
        total_market_value: 80000,
        priced_cost_basis: 76012.5,
        unrealized_pnl: 3987.5,
        unrealized_pnl_percent: 5.25,
      },
      completeness: {
        is_complete: true,
        completeness_ratio: 1.0,
        total_holdings_count: 1,
        priced_holdings_count: 1,
        unpriced_holdings_count: 0,
        has_stale_prices: false,
        has_simulated_prices: true,
        unpriced_positions: [],
      },
      holdings: [
        {
          holding_id: 'h-new-123',
          symbol: 'INFY',
          exchange: 'NSE',
          quantity: 50,
          average_buy_price: 1520.25,
          cost_basis: 76012.5,
          current_price: 1600.0,
          market_value: 80000,
          unrealized_pnl: 3987.5,
          unrealized_pnl_percent: 5.25,
          market_value_weight_percent: 100.0,
          cost_basis_weight_percent: 100.0,
          pricing_status: 'AVAILABLE',
          is_simulated: true,
          is_stale: false,
          sector: 'IT',
          asset_class: 'EQUITY',
        },
      ],
    };

    beforeEach(() => {
      vi.mocked(analyticsApi.fetchPortfolioAnalytics).mockResolvedValue(mockEmptyAnalytics);
      vi.mocked(analyticsApi.fetchPortfolioInsights).mockResolvedValue({
        portfolio_id: 'port-demo-1',
        insights: [],
        total_insights: 0,
        generated_at: '2026-10-11T12:00:00Z',
        is_sample_portfolio: false,
        disclaimer: 'Deterministic observations only',
      });
    });

    it('opens add holding modal from HoldingsTable header button', async () => {
      render(
        <PortfolioProvider>
          <PortfolioHub />
        </PortfolioProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('add-holding-btn')).toBeInTheDocument();
      });

      expect(screen.queryByTestId('add-holding-modal')).not.toBeInTheDocument();

      fireEvent.click(screen.getByTestId('add-holding-btn'));
      expect(screen.getByTestId('add-holding-modal')).toBeInTheDocument();
    });

    it('opens add holding modal from empty holdings table action', async () => {
      render(
        <PortfolioProvider>
          <PortfolioHub />
        </PortfolioProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('empty-add-holding-btn')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByTestId('empty-add-holding-btn'));
      expect(screen.getByTestId('add-holding-modal')).toBeInTheDocument();
    });

    it('submits holding from PortfolioHub, refreshes analytics, and shows success banner', async () => {
      vi.mocked(portfoliosApi.addHolding).mockResolvedValueOnce(mockHoldingResponse);

      render(
        <PortfolioProvider>
          <PortfolioHub />
        </PortfolioProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('empty-add-holding-btn')).toBeInTheDocument();
      });

      // Open modal
      fireEvent.click(screen.getByTestId('empty-add-holding-btn'));

      // Fill in holding details
      fireEvent.change(screen.getByTestId('holding-symbol-input'), {
        target: { value: 'INFY' },
      });
      fireEvent.change(screen.getByTestId('holding-quantity-input'), {
        target: { value: '50' },
      });
      fireEvent.change(screen.getByTestId('holding-price-input'), {
        target: { value: '1520.25' },
      });

      // Update mock analytics to return the new position on refresh
      vi.mocked(analyticsApi.fetchPortfolioAnalytics).mockResolvedValueOnce(mockUpdatedAnalytics);

      // Submit
      fireEvent.click(screen.getByTestId('submit-add-holding-btn'));

      // Modal closes, banner appears, analytics refreshed
      await waitFor(() => {
        expect(screen.queryByTestId('add-holding-modal')).not.toBeInTheDocument();
        expect(screen.getByTestId('holding-add-success-banner')).toBeInTheDocument();
        expect(
          screen.getByText(/Added 50 shares of INFY to Growth Tech Basket/i)
        ).toBeInTheDocument();
      });

      // Dismiss success banner
      fireEvent.click(screen.getByLabelText(/dismiss holding success message/i));
      expect(screen.queryByTestId('holding-add-success-banner')).not.toBeInTheDocument();
    });
  });
});
