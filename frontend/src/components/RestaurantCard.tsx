import type { Restaurant } from '../types';
import { getPriceDisplay } from '../utils';
import './RestaurantCard.css';

type RestaurantCardProps = {
  restaurant: Restaurant;
  isSelected: boolean;
  onSelect: () => void;
  onLike: () => void;
  onSave: () => void;
  isLiked?: boolean;
  isSaved?: boolean;
  rank?: number;
};

export function RestaurantCard({
  restaurant,
  isSelected,
  onSelect,
  onLike,
  onSave,
  isLiked = false,
  isSaved = false,
  rank,
}: RestaurantCardProps) {
  return (
    <article
      className={`restaurant-card ${isSelected ? 'restaurant-card--selected' : ''}`}
      onClick={onSelect}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && onSelect()}
    >
      {rank && rank <= 3 && (
        <div className={`restaurant-card__rank restaurant-card__rank--${rank}`}>
          #{rank}
        </div>
      )}
      
      {restaurant.is_new && (
        <span className="restaurant-card__badge restaurant-card__badge--new">NEW</span>
      )}

      <div className="restaurant-card__header">
        <div className="restaurant-card__title-row">
          <h3 className="restaurant-card__name">{restaurant.name}</h3>
          <div className="restaurant-card__buzz">
            <span className="restaurant-card__buzz-icon">🔥</span>
            <span className="restaurant-card__buzz-score">{restaurant.buzz_score.toFixed(1)}</span>
          </div>
        </div>
        
        <div className="restaurant-card__meta">
          <span className="restaurant-card__cuisine">{restaurant.cuisine_type}</span>
          <span className="restaurant-card__price">{getPriceDisplay(restaurant.price_range)}</span>
        </div>
      </div>

      <p className="restaurant-card__summary">{restaurant.summary}</p>

      <div className="restaurant-card__stats">
        <div className="restaurant-card__stat">
          <span className="restaurant-card__stat-icon">❤️</span>
          <span>{restaurant.sentiment.toFixed(1)}/10</span>
        </div>
        <div className="restaurant-card__stat">
          <span className="restaurant-card__stat-icon">💬</span>
          <span>{restaurant.mentions}</span>
        </div>
        {restaurant.sources && restaurant.sources.length > 0 && (
          <div className="restaurant-card__stat">
            <span className="restaurant-card__stat-icon">📰</span>
            <span>{restaurant.sources.length}</span>
          </div>
        )}
      </div>

      <div className="restaurant-card__actions">
        <button
          className={`restaurant-card__action ${isLiked ? 'restaurant-card__action--active' : ''}`}
          onClick={(e) => { e.stopPropagation(); onLike(); }}
          title="Like"
        >
          <span>{isLiked ? '❤️' : '🤍'}</span>
          <span>{restaurant.user_likes}</span>
        </button>
        <button
          className={`restaurant-card__action ${isSaved ? 'restaurant-card__action--active' : ''}`}
          onClick={(e) => { e.stopPropagation(); onSave(); }}
          title="Save"
        >
          <span>{isSaved ? '🔖' : '📌'}</span>
          <span>{restaurant.user_saves}</span>
        </button>
        <button
          className="restaurant-card__action"
          onClick={(e) => { e.stopPropagation(); navigator.share?.({ title: restaurant.name, text: restaurant.summary }); }}
          title="Share"
        >
          <span>🔗</span>
        </button>
      </div>
    </article>
  );
}
