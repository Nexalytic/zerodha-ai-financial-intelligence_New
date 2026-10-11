import React, { useState, useEffect } from 'react';
import { X, Layers, AlertCircle, Plus } from 'lucide-react';
import { addHolding } from '../../api/portfolios';
import { parseApiError } from '../../api/client';

const SYMBOL_REGEX = /^[A-Z0-9&-]{1,20}$/;
const COMMON_SECTORS = [
  'Financial Services',
  'IT',
  'Energy',
  'Automobile',
  'Consumer Goods',
  'Construction',
  'Telecommunication',
  'Healthcare',
  'Metals & Mining',
  'Utilities',
];

export interface AddHoldingModalProps {
  isOpen: boolean;
  onClose: () => void;
  portfolioId: string;
  portfolioName: string;
  onHoldingAdded?: (symbol: string, quantity: number) => void;
}

export const AddHoldingModal: React.FC<AddHoldingModalProps> = ({
  isOpen,
  onClose,
  portfolioId,
  portfolioName,
  onHoldingAdded,
}) => {
  const [symbol, setSymbol] = useState<string>('');
  const [exchange, setExchange] = useState<string>('NSE');
  const [quantity, setQuantity] = useState<string>('');
  const [averageBuyPrice, setAverageBuyPrice] = useState<string>('');
  const [sector, setSector] = useState<string>('');
  const [assetClass, setAssetClass] = useState<string>('EQUITY');

  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Reset form when modal opens or closes
  useEffect(() => {
    if (isOpen) {
      setSymbol('');
      setExchange('NSE');
      setQuantity('');
      setAverageBuyPrice('');
      setSector('');
      setAssetClass('EQUITY');
      setErrorMessage(null);
      setIsSubmitting(false);
    }
  }, [isOpen]);

  if (!isOpen) {
    return null;
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    const cleanSymbol = symbol.trim().toUpperCase();
    if (!cleanSymbol) {
      setErrorMessage('Stock symbol is required (1-20 characters).');
      return;
    }

    if (!SYMBOL_REGEX.test(cleanSymbol)) {
      setErrorMessage(
        'Symbol must be 1-20 alphanumeric characters, &, or - (e.g., RELIANCE, M&M, TCS).'
      );
      return;
    }

    if (!['NSE', 'BSE'].includes(exchange)) {
      setErrorMessage('Exchange must be either NSE or BSE.');
      return;
    }

    const qtyNum = Number(quantity);
    if (!quantity || isNaN(qtyNum) || !Number.isInteger(qtyNum) || qtyNum <= 0) {
      setErrorMessage('Quantity must be a positive whole number greater than 0.');
      return;
    }

    const priceNum = Number(averageBuyPrice);
    if (
      !averageBuyPrice ||
      isNaN(priceNum) ||
      !isFinite(priceNum) ||
      priceNum <= 0
    ) {
      setErrorMessage(
        'Average buy price must be a positive monetary amount greater than 0.'
      );
      return;
    }

    const cleanSector = sector.trim() || null;
    if (cleanSector && cleanSector.length > 50) {
      setErrorMessage('Sector cannot exceed 50 characters.');
      return;
    }

    if (!['EQUITY', 'ETF', 'MUTUAL_FUND'].includes(assetClass)) {
      setErrorMessage('Asset class must be EQUITY, ETF, or MUTUAL_FUND.');
      return;
    }

    setIsSubmitting(true);
    try {
      await addHolding(portfolioId, {
        symbol: cleanSymbol,
        exchange,
        quantity: qtyNum,
        average_buy_price: priceNum,
        sector: cleanSector,
        asset_class: assetClass,
      });

      if (onHoldingAdded) {
        onHoldingAdded(cleanSymbol, qtyNum);
      }
      onClose();
    } catch (err: unknown) {
      const parsed = parseApiError(err);
      setErrorMessage(
        parsed.message || 'Failed to add holding position. Please try again.'
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      data-testid="add-holding-modal-backdrop"
      className="fixed inset-0 z-50 bg-gray-900/50 backdrop-blur-xs flex items-center justify-center p-4 overflow-y-auto"
      onClick={(e) => {
        if (e.target === e.currentTarget && !isSubmitting) {
          onClose();
        }
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="add-holding-modal-title"
        data-testid="add-holding-modal"
        className="bg-white rounded-2xl shadow-xl border border-gray-200 w-full max-w-lg overflow-hidden animate-in fade-in zoom-in-95 duration-150 my-8"
      >
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between bg-gray-50/50">
          <div className="flex items-center space-x-2.5">
            <div className="w-8 h-8 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center">
              <Layers className="w-4 h-4" />
            </div>
            <div>
              <h3
                id="add-holding-modal-title"
                className="text-base font-bold text-gray-900 tracking-tight"
              >
                Add Position to Portfolio
              </h3>
              <p className="text-[11px] text-gray-500 truncate max-w-xs sm:max-w-sm">
                Target: <span className="font-semibold text-gray-700">{portfolioName}</span>
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isSubmitting}
            data-testid="close-add-holding-modal"
            aria-label="Close modal"
            className="text-gray-400 hover:text-gray-600 p-1 rounded-lg hover:bg-gray-100 transition cursor-pointer disabled:opacity-50"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Form Body */}
        <form
          onSubmit={handleSubmit}
          noValidate
          data-testid="add-holding-form"
          className="p-6 space-y-4"
        >
          {errorMessage && (
            <div
              role="alert"
              data-testid="add-holding-error"
              className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-800 flex items-start space-x-2"
            >
              <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0 mt-0.5" />
              <div className="leading-relaxed">{errorMessage}</div>
            </div>
          )}

          {/* Row 1: Symbol & Exchange */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="sm:col-span-2 space-y-1.5">
              <label
                htmlFor="holding-symbol-input"
                className="block text-xs font-semibold text-gray-700"
              >
                Stock Symbol <span className="text-rose-500">*</span>
              </label>
              <input
                id="holding-symbol-input"
                data-testid="holding-symbol-input"
                type="text"
                required
                maxLength={20}
                value={symbol}
                onChange={(e) => setSymbol(e.target.value.toUpperCase())}
                placeholder="e.g., RELIANCE, TCS, INFY"
                disabled={isSubmitting}
                className="w-full px-3 py-2 text-xs font-mono font-medium border border-gray-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition disabled:bg-gray-50 uppercase"
              />
            </div>

            <div className="space-y-1.5">
              <label
                htmlFor="holding-exchange-select"
                className="block text-xs font-semibold text-gray-700"
              >
                Exchange <span className="text-rose-500">*</span>
              </label>
              <select
                id="holding-exchange-select"
                data-testid="holding-exchange-select"
                value={exchange}
                onChange={(e) => setExchange(e.target.value)}
                disabled={isSubmitting}
                className="w-full px-3 py-2 text-xs border border-gray-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition bg-white disabled:bg-gray-50"
              >
                <option value="NSE">NSE</option>
                <option value="BSE">BSE</option>
              </select>
            </div>
          </div>

          {/* Row 2: Quantity & Average Buy Price */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <label
                htmlFor="holding-quantity-input"
                className="block text-xs font-semibold text-gray-700"
              >
                Quantity (Shares) <span className="text-rose-500">*</span>
              </label>
              <input
                id="holding-quantity-input"
                data-testid="holding-quantity-input"
                type="number"
                min="1"
                step="1"
                required
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                placeholder="e.g., 25"
                disabled={isSubmitting}
                className="w-full px-3 py-2 text-xs font-mono border border-gray-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition disabled:bg-gray-50"
              />
            </div>

            <div className="space-y-1.5">
              <label
                htmlFor="holding-price-input"
                className="block text-xs font-semibold text-gray-700"
              >
                Avg Buy Price (₹) <span className="text-rose-500">*</span>
              </label>
              <input
                id="holding-price-input"
                data-testid="holding-price-input"
                type="number"
                min="0.01"
                step="0.01"
                required
                value={averageBuyPrice}
                onChange={(e) => setAverageBuyPrice(e.target.value)}
                placeholder="e.g., 2850.50"
                disabled={isSubmitting}
                className="w-full px-3 py-2 text-xs font-mono border border-gray-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition disabled:bg-gray-50"
              />
            </div>
          </div>

          {/* Row 3: Sector & Asset Class */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <label
                htmlFor="holding-sector-input"
                className="block text-xs font-semibold text-gray-700"
              >
                Sector <span className="text-gray-400 font-normal">(Optional)</span>
              </label>
              <input
                id="holding-sector-input"
                data-testid="holding-sector-input"
                type="text"
                list="sector-suggestions"
                maxLength={50}
                value={sector}
                onChange={(e) => setSector(e.target.value)}
                placeholder="e.g., IT, Energy"
                disabled={isSubmitting}
                className="w-full px-3 py-2 text-xs border border-gray-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition disabled:bg-gray-50"
              />
              <datalist id="sector-suggestions">
                {COMMON_SECTORS.map((sec) => (
                  <option key={sec} value={sec} />
                ))}
              </datalist>
            </div>

            <div className="space-y-1.5">
              <label
                htmlFor="holding-asset-class-select"
                className="block text-xs font-semibold text-gray-700"
              >
                Asset Class <span className="text-rose-500">*</span>
              </label>
              <select
                id="holding-asset-class-select"
                data-testid="holding-asset-class-select"
                value={assetClass}
                onChange={(e) => setAssetClass(e.target.value)}
                disabled={isSubmitting}
                className="w-full px-3 py-2 text-xs border border-gray-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition bg-white disabled:bg-gray-50"
              >
                <option value="EQUITY">EQUITY</option>
                <option value="ETF">ETF</option>
                <option value="MUTUAL_FUND">MUTUAL_FUND</option>
              </select>
            </div>
          </div>

          {/* Modal Actions */}
          <div className="pt-3 border-t border-gray-100 flex items-center justify-end space-x-2.5">
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
              data-testid="cancel-add-holding-btn"
              className="px-4 py-2 text-xs font-semibold text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded-lg transition cursor-pointer disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              data-testid="submit-add-holding-btn"
              className="inline-flex items-center space-x-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-lg shadow-xs transition cursor-pointer disabled:opacity-50"
            >
              {isSubmitting ? (
                <>
                  <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  <span>Adding Position...</span>
                </>
              ) : (
                <>
                  <Plus className="w-3.5 h-3.5" />
                  <span>Add Holding</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
