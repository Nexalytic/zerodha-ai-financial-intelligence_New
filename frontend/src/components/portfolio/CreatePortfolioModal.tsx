import React, { useState, useEffect } from 'react';
import { X, Briefcase, AlertCircle, Plus } from 'lucide-react';
import { createPortfolio } from '../../api/portfolios';
import { usePortfolio } from '../../context/PortfolioContext';
import { parseApiError } from '../../api/client';

export interface CreatePortfolioModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCreated?: (portfolioName: string) => void;
}

export const CreatePortfolioModal: React.FC<CreatePortfolioModalProps> = ({
  isOpen,
  onClose,
  onCreated,
}) => {
  const { refreshPortfolios, setActivePortfolioId } = usePortfolio();

  const [name, setName] = useState<string>('');
  const [description, setDescription] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Reset form when opened or closed
  useEffect(() => {
    if (isOpen) {
      setName('');
      setDescription('');
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

    const trimmedName = name.trim();
    if (!trimmedName) {
      setErrorMessage('Portfolio name is required (1-100 characters).');
      return;
    }

    if (trimmedName.length > 100) {
      setErrorMessage('Portfolio name cannot exceed 100 characters.');
      return;
    }

    const trimmedDescription = description.trim();
    if (trimmedDescription.length > 255) {
      setErrorMessage('Portfolio description cannot exceed 255 characters.');
      return;
    }

    setIsSubmitting(true);
    try {
      const created = await createPortfolio({
        name: trimmedName,
        description: trimmedDescription || null,
        is_sample: false,
      });

      await refreshPortfolios();
      if (created?.id) {
        setActivePortfolioId(created.id);
      }

      if (onCreated) {
        onCreated(trimmedName);
      }
      onClose();
    } catch (err: unknown) {
      const parsed = parseApiError(err);
      setErrorMessage(parsed.message || 'Failed to create portfolio. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      data-testid="create-portfolio-modal-backdrop"
      className="fixed inset-0 z-50 bg-gray-900/50 backdrop-blur-xs flex items-center justify-center p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget && !isSubmitting) {
          onClose();
        }
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="create-portfolio-modal-title"
        data-testid="create-portfolio-modal"
        className="bg-white rounded-2xl shadow-xl border border-gray-200 w-full max-w-md overflow-hidden animate-in fade-in zoom-in-95 duration-150"
      >
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between bg-gray-50/50">
          <div className="flex items-center space-x-2.5">
            <div className="w-8 h-8 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center">
              <Briefcase className="w-4 h-4" />
            </div>
            <div>
              <h3
                id="create-portfolio-modal-title"
                className="text-base font-bold text-gray-900 tracking-tight"
              >
                Create New Portfolio
              </h3>
              <p className="text-[11px] text-gray-500">
                Setup a new investment container for your holdings
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isSubmitting}
            data-testid="close-create-portfolio-modal"
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
          data-testid="create-portfolio-form"
          className="p-6 space-y-4"
        >
          {errorMessage && (
            <div
              role="alert"
              data-testid="create-portfolio-error"
              className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-800 flex items-start space-x-2"
            >
              <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0 mt-0.5" />
              <div className="leading-relaxed">{errorMessage}</div>
            </div>
          )}

          <div className="space-y-1.5">
            <label
              htmlFor="portfolio-name-input"
              className="block text-xs font-semibold text-gray-700"
            >
              Portfolio Name <span className="text-rose-500">*</span>
            </label>
            <input
              id="portfolio-name-input"
              data-testid="portfolio-name-input"
              type="text"
              required
              maxLength={100}
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., Growth Momentum Basket"
              disabled={isSubmitting}
              className="w-full px-3 py-2 text-xs border border-gray-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition disabled:bg-gray-50 disabled:text-gray-400"
            />
            <p className="text-[10px] text-gray-400 text-right">
              {name.length}/100 characters
            </p>
          </div>

          <div className="space-y-1.5">
            <label
              htmlFor="portfolio-description-input"
              className="block text-xs font-semibold text-gray-700"
            >
              Description <span className="text-gray-400 font-normal">(Optional)</span>
            </label>
            <textarea
              id="portfolio-description-input"
              data-testid="portfolio-description-input"
              rows={3}
              maxLength={255}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="e.g., Core technology and manufacturing holdings for long-term compounding"
              disabled={isSubmitting}
              className="w-full px-3 py-2 text-xs border border-gray-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition disabled:bg-gray-50 disabled:text-gray-400 resize-none"
            />
            <p className="text-[10px] text-gray-400 text-right">
              {description.length}/255 characters
            </p>
          </div>

          <div className="pt-2 flex items-center justify-end space-x-2.5">
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
              data-testid="cancel-create-portfolio-btn"
              className="px-4 py-2 text-xs font-semibold text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded-lg transition cursor-pointer disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              data-testid="submit-create-portfolio-btn"
              className="inline-flex items-center space-x-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-lg shadow-xs transition cursor-pointer disabled:opacity-50"
            >
              {isSubmitting ? (
                <>
                  <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  <span>Creating Portfolio...</span>
                </>
              ) : (
                <>
                  <Plus className="w-3.5 h-3.5" />
                  <span>Create Portfolio</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
