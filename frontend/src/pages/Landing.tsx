import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, Sparkles, TrendingUp, Utensils } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { useTrending } from '@/hooks';

/**
 * Landing page with hero section and search.
 * Bold, Neobrutalism-styled entry point.
 */
export function Landing() {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const { data: trending = [] } = useTrending();

  const handleSearch = (searchQuery: string) => {
    const q = searchQuery.trim();
    if (q) {
      navigate(`/search?q=${encodeURIComponent(q)}`);
    } else {
      navigate('/search');
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    handleSearch(query);
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Hero Section */}
      <div className="relative overflow-hidden">
        {/* Background Pattern */}
        <div className="absolute inset-0 bg-[linear-gradient(45deg,transparent_25%,var(--main)_25%,var(--main)_50%,transparent_50%,transparent_75%,var(--main)_75%)] bg-[length:64px_64px] opacity-5" />
        
        <div className="relative mx-auto max-w-4xl px-4 py-24 sm:py-32">
          {/* Logo & Title */}
          <div className="mb-12 text-center">
            <div className="mb-4 inline-flex items-center gap-3 rounded-base border-2 border-border bg-main px-4 py-2 shadow-shadow">
              <Utensils className="h-8 w-8" />
              <span className="text-3xl font-heading font-black tracking-tight">
                BELLY-BUZZ
              </span>
            </div>
            <h1 className="mt-8 text-4xl font-heading font-black tracking-tight sm:text-6xl">
              Discover restaurants
              <br />
              <span className="relative">
                people actually love
                <Sparkles className="absolute -right-8 -top-4 h-6 w-6 text-main" />
              </span>
            </h1>
            <p className="mx-auto mt-6 max-w-xl text-lg text-muted-foreground">
              AI-powered Toronto restaurant recommendations from real conversations. 
              Find your next favorite spot based on what people are actually saying on Reddit and food blogs.
            </p>
          </div>

          {/* Search Bar */}
          <form onSubmit={handleSubmit} className="mx-auto max-w-2xl">
            <div className="flex gap-3">
              <div className="relative flex-1">
                <Search className="absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground" />
                <Input
                  type="text"
                  placeholder="Best ramen in Toronto, hidden gems in Kensington..."
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  className="h-14 pl-12 text-lg"
                />
              </div>
              <Button type="submit" size="lg" className="h-14 px-8 text-lg font-bold">
                Search
              </Button>
            </div>
          </form>

          {/* Trending Pills */}
          <div className="mt-8 text-center">
            <div className="mb-4 flex items-center justify-center gap-2 text-sm text-muted-foreground">
              <TrendingUp className="h-4 w-4" />
              <span className="font-medium">Trending searches</span>
            </div>
            <div className="flex flex-wrap justify-center gap-2">
              {trending.map((term) => (
                <Badge
                  key={term}
                  variant="neutral"
                  className="cursor-pointer px-4 py-2 text-sm transition-transform hover:scale-105"
                  onClick={() => handleSearch(term)}
                >
                  {term}
                </Badge>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Features Section */}
      <div className="border-t-2 border-border bg-bw py-16">
        <div className="mx-auto max-w-4xl px-4">
          <div className="grid gap-6 sm:grid-cols-3">
            <FeatureCard
              icon={<Sparkles className="h-6 w-6" />}
              title="AI-Powered"
              description="Smart recommendations from analyzing real conversations and reviews"
            />
            <FeatureCard
              icon={<TrendingUp className="h-6 w-6" />}
              title="Real Buzz"
              description="See what people are actually saying, not just star ratings"
            />
            <FeatureCard
              icon={<Utensils className="h-6 w-6" />}
              title="Dish Specific"
              description="Find the best specific dishes, not just restaurants"
            />
          </div>
        </div>
      </div>
    </div>
  );
}

function FeatureCard({
  icon,
  title,
  description,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
}) {
  return (
    <div className="rounded-base border-2 border-border bg-background p-6 shadow-shadow">
      <div className="mb-3 inline-flex rounded-base border-2 border-border bg-main p-2">
        {icon}
      </div>
      <h3 className="mb-2 font-heading text-lg font-bold">{title}</h3>
      <p className="text-sm text-muted-foreground">{description}</p>
    </div>
  );
}
