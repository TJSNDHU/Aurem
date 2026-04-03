import React, { useState, useEffect } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Helmet } from 'react-helmet-async';
import { 
  Calendar, User, Tag, Clock, ChevronLeft, Share2, 
  Facebook, Twitter, Loader2, ArrowRight, Eye, ShoppingCart,
  BookOpen, ExternalLink
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

// Shoppable Product Card for public display
const ShoppableProductEmbed = ({ product }) => {
  if (!product) return null;
  
  return (
    <div className="border-2 border-[#F8A5B8]/30 rounded-2xl p-4 bg-gradient-to-r from-[#FDF9F9] to-white my-6 hover:shadow-lg transition-shadow">
      <div className="flex items-center gap-4">
        <div className="w-24 h-24 bg-gray-100 rounded-xl overflow-hidden flex-shrink-0">
          {product.images?.[0] ? (
            <img src={product.images[0]} alt={product.name} className="w-full h-full object-cover" />
          ) : (
            <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-[#F8A5B8]/20 to-[#F8A5B8]/5">
              <span className="text-2xl font-bold text-[#F8A5B8]/50">R</span>
            </div>
          )}
        </div>
        <div className="flex-1 min-w-0">
          <Badge className="bg-[#F8A5B8]/20 text-[#F8A5B8] mb-2">Featured Product</Badge>
          <h4 className="font-semibold text-[#2D2A2E] text-lg">{product.name}</h4>
          <p className="text-2xl font-bold text-[#F8A5B8] mt-1">${product.price?.toFixed(2)}</p>
        </div>
        <Link to={`/products/${product.slug || product.id}`}>
          <Button className="bg-[#F8A5B8] hover:bg-[#E89AAB] text-white">
            <ShoppingCart className="w-4 h-4 mr-2" />
            Shop Now
          </Button>
        </Link>
      </div>
    </div>
  );
};

// References Section
const ReferencesSection = ({ references }) => {
  if (!references || references.length === 0) return null;
  
  return (
    <div className="mt-12 pt-8 border-t border-gray-200">
      <h3 className="flex items-center gap-2 text-xl font-bold text-[#2D2A2E] mb-6">
        <BookOpen className="w-5 h-5 text-purple-600" />
        References & Citations
      </h3>
      <div className="bg-gradient-to-r from-purple-50 to-indigo-50 rounded-xl p-6 space-y-4">
        {references.map((ref, index) => (
          <div key={index} className="flex items-start gap-3">
            <span className="w-6 h-6 bg-[#2D2A2E] text-white rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5">
              {index + 1}
            </span>
            <div className="flex-1">
              <p className="font-medium text-[#2D2A2E]">{ref.title}</p>
              {ref.source && (
                <p className="text-sm text-[#5A5A5A] mt-1">{ref.source}{ref.year && ` (${ref.year})`}</p>
              )}
              {ref.url && (
                <a 
                  href={ref.url} 
                  target="_blank" 
                  rel="noopener noreferrer" 
                  className="text-sm text-purple-600 hover:underline inline-flex items-center gap-1 mt-1"
                >
                  View Source <ExternalLink className="w-3 h-3" />
                </a>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

// Blog List Page Component
export const BlogListPage = () => {
  const [posts, setPosts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [categories, setCategories] = useState([]);
  const [selectedCategory, setSelectedCategory] = useState(null);

  useEffect(() => {
    const fetchPosts = async () => {
      try {
        const [postsRes, catsRes] = await Promise.all([
          axios.get(`${API}/blog/posts`),
          axios.get(`${API}/blog/categories`)
        ]);
        setPosts(postsRes.data.posts || []);
        setCategories(catsRes.data.categories || []);
      } catch (error) {
        console.error('Failed to fetch blog posts:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchPosts();
  }, []);

  const filteredPosts = selectedCategory 
    ? posts.filter(p => p.category === selectedCategory)
    : posts;

  return (
    <>
      <Helmet>
        <title>Blog | ReRoots Skincare - Expert Tips & Guides</title>
        <meta name="description" content="Discover expert skincare tips, ingredient guides, and beauty routines from ReRoots. Learn about PDRN, anti-aging solutions, and more." />
        <meta property="og:title" content="ReRoots Skincare Blog" />
        <meta property="og:description" content="Expert skincare tips, ingredient guides, and beauty routines" />
        <meta property="og:type" content="website" />
      </Helmet>

      <div className="min-h-screen bg-gradient-to-b from-[#FDF9F9] to-white">
        {/* Hero Section */}
        <div className="bg-gradient-to-r from-[#2D2A2E] to-[#3D393D] text-white py-16 px-4">
          <div className="max-w-6xl mx-auto text-center">
            <h1 className="text-4xl md:text-5xl font-bold mb-4">ReRoots Blog</h1>
            <p className="text-lg text-white/80 max-w-2xl mx-auto">
              Expert skincare knowledge, ingredient science, and beauty tips to help you achieve your healthiest skin
            </p>
          </div>
        </div>

        <div className="max-w-6xl mx-auto px-4 py-12">
          {/* Categories Filter */}
          {categories.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-8 justify-center">
              <Button
                variant={selectedCategory === null ? "default" : "outline"}
                size="sm"
                onClick={() => setSelectedCategory(null)}
                className={selectedCategory === null ? "bg-[#F8A5B8] hover:bg-[#E89AAB]" : ""}
              >
                All Posts
              </Button>
              {categories.map(cat => (
                <Button
                  key={cat.name}
                  variant={selectedCategory === cat.name ? "default" : "outline"}
                  size="sm"
                  onClick={() => setSelectedCategory(cat.name)}
                  className={selectedCategory === cat.name ? "bg-[#F8A5B8] hover:bg-[#E89AAB]" : ""}
                >
                  {cat.name} ({cat.count})
                </Button>
              ))}
            </div>
          )}

          {/* Posts Grid */}
          {loading ? (
            <div className="flex items-center justify-center py-20">
              <Loader2 className="w-8 h-8 animate-spin text-[#F8A5B8]" />
            </div>
          ) : filteredPosts.length === 0 ? (
            <div className="text-center py-20">
              <h2 className="text-xl font-semibold text-[#2D2A2E] mb-2">No blog posts yet</h2>
              <p className="text-[#5A5A5A]">Check back soon for new content!</p>
            </div>
          ) : (
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
              {filteredPosts.map(post => (
                <Link 
                  key={post.id} 
                  to={`/blog/${post.slug}`}
                  className="group"
                  data-testid={`blog-post-${post.slug}`}
                >
                  <Card className="h-full overflow-hidden hover:shadow-lg transition-all duration-300 group-hover:-translate-y-1">
                    {/* Featured Image */}
                    <div className="aspect-video bg-gray-100 overflow-hidden">
                      {post.featured_image ? (
                        <img 
                          src={post.featured_image} 
                          alt={post.title}
                          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                        />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-[#F8A5B8]/20 to-[#F8A5B8]/5">
                          <span className="text-4xl font-bold text-[#F8A5B8]/30">R</span>
                        </div>
                      )}
                    </div>

                    <CardContent className="p-5">
                      {/* Category Badge */}
                      <Badge variant="secondary" className="mb-3 text-xs">
                        {post.category}
                      </Badge>

                      {/* Title */}
                      <h2 className="font-semibold text-lg text-[#2D2A2E] mb-2 line-clamp-2 group-hover:text-[#F8A5B8] transition-colors">
                        {post.title}
                      </h2>

                      {/* Excerpt */}
                      <p className="text-sm text-[#5A5A5A] line-clamp-3 mb-4">
                        {post.excerpt}
                      </p>

                      {/* Meta Info */}
                      <div className="flex items-center justify-between text-xs text-[#5A5A5A]">
                        <div className="flex items-center gap-3">
                          <span className="flex items-center gap-1">
                            <Calendar className="w-3 h-3" />
                            {new Date(post.published_at).toLocaleDateString('en-US', {
                              month: 'short',
                              day: 'numeric',
                              year: 'numeric'
                            })}
                          </span>
                          <span className="flex items-center gap-1">
                            <Eye className="w-3 h-3" />
                            {post.views || 0}
                          </span>
                        </div>
                        <ArrowRight className="w-4 h-4 text-[#F8A5B8] opacity-0 group-hover:opacity-100 transition-opacity" />
                      </div>
                    </CardContent>
                  </Card>
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  );
};

// Single Blog Post Page Component
export const BlogPostPage = () => {
  const { slug } = useParams();
  const navigate = useNavigate();
  const [post, setPost] = useState(null);
  const [loading, setLoading] = useState(true);
  const [relatedPosts, setRelatedPosts] = useState([]);

  useEffect(() => {
    const fetchPost = async () => {
      try {
        const res = await axios.get(`${API}/blog/posts/${slug}`);
        setPost(res.data);

        // Fetch related posts
        const allPosts = await axios.get(`${API}/blog/posts`);
        const related = allPosts.data.posts
          .filter(p => p.slug !== slug && p.category === res.data.category)
          .slice(0, 3);
        setRelatedPosts(related);
      } catch (error) {
        console.error('Failed to fetch blog post:', error);
        if (error.response?.status === 404) {
          navigate('/blog');
        }
      } finally {
        setLoading(false);
      }
    };
    fetchPost();
  }, [slug, navigate]);

  const shareUrl = typeof window !== 'undefined' ? window.location.href : '';

  const handleShare = (platform) => {
    const title = encodeURIComponent(post?.title || '');
    const url = encodeURIComponent(shareUrl);
    
    const shareUrls = {
      twitter: `https://twitter.com/intent/tweet?text=${title}&url=${url}`,
      facebook: `https://www.facebook.com/sharer/sharer.php?u=${url}`,
      copy: shareUrl
    };

    if (platform === 'copy') {
      navigator.clipboard.writeText(shareUrl);
      alert('Link copied to clipboard!');
    } else {
      window.open(shareUrls[platform], '_blank', 'width=600,height=400');
    }
  };

  // Generate Schema.org JSON-LD
  const generateSchemaMarkup = () => {
    if (!post) return null;
    
    const schema = {
      "@context": "https://schema.org",
      "@type": post.schema_type || "Article",
      "headline": post.title,
      "description": post.meta_description || post.excerpt,
      "image": post.featured_image,
      "author": {
        "@type": "Person",
        "name": post.author_name || "ReRoots Team"
      },
      "publisher": {
        "@type": "Organization",
        "name": "ReRoots Skincare",
        "logo": {
          "@type": "ImageObject",
          "url": "https://reroots.ca/logo.png"
        }
      },
      "datePublished": post.published_at,
      "dateModified": post.updated_at || post.published_at,
      "mainEntityOfPage": {
        "@type": "WebPage",
        "@id": shareUrl
      }
    };

    // Add citations if present
    if (post.references && post.references.length > 0) {
      schema.citation = post.references.map(ref => ({
        "@type": "CreativeWork",
        "name": ref.title,
        "url": ref.url
      }));
    }

    return schema;
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-[#F8A5B8]" />
      </div>
    );
  }

  if (!post) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center">
        <h1 className="text-2xl font-bold mb-4">Post not found</h1>
        <Link to="/blog" className="text-[#F8A5B8] hover:underline">
          Back to Blog
        </Link>
      </div>
    );
  }

  return (
    <>
      <Helmet>
        <title>{post.meta_title || post.title} | ReRoots Blog</title>
        <meta name="description" content={post.meta_description || post.excerpt} />
        <meta property="og:title" content={post.meta_title || post.title} />
        <meta property="og:description" content={post.meta_description || post.excerpt} />
        <meta property="og:type" content="article" />
        <meta property="og:image" content={post.featured_image} />
        <meta property="article:published_time" content={post.published_at} />
        <meta property="article:author" content={post.author_name} />
        <link rel="canonical" href={shareUrl} />
        {/* Schema.org JSON-LD */}
        <script type="application/ld+json">
          {JSON.stringify(generateSchemaMarkup())}
        </script>
      </Helmet>

      <article className="min-h-screen bg-white" data-testid="blog-post-article">
        {/* Back Button */}
        <div className="max-w-4xl mx-auto px-4 pt-6">
          <Link 
            to="/blog" 
            className="inline-flex items-center text-[#5A5A5A] hover:text-[#F8A5B8] transition-colors"
          >
            <ChevronLeft className="w-4 h-4 mr-1" />
            Back to Blog
          </Link>
        </div>

        {/* Featured Image */}
        {post.featured_image && (
          <div className="max-w-5xl mx-auto px-4 mt-6">
            <div className="aspect-[21/9] rounded-2xl overflow-hidden">
              <img 
                src={post.featured_image} 
                alt={post.title}
                className="w-full h-full object-cover"
              />
            </div>
          </div>
        )}

        {/* Article Content */}
        <div className="max-w-4xl mx-auto px-4 py-8">
          {/* Category & Date */}
          <div className="flex flex-wrap items-center gap-3 mb-4">
            <Badge className="bg-[#F8A5B8]/20 text-[#F8A5B8] hover:bg-[#F8A5B8]/30">
              {post.category}
            </Badge>
            <span className="text-sm text-[#5A5A5A] flex items-center gap-1">
              <Calendar className="w-4 h-4" />
              {new Date(post.published_at).toLocaleDateString('en-US', {
                month: 'long',
                day: 'numeric',
                year: 'numeric'
              })}
            </span>
            <span className="text-sm text-[#5A5A5A] flex items-center gap-1">
              <Clock className="w-4 h-4" />
              {Math.ceil(post.content.split(' ').length / 200)} min read
            </span>
            {post.focus_keyword && (
              <Badge variant="outline" className="text-xs">
                Focus: {post.focus_keyword}
              </Badge>
            )}
          </div>

          {/* Title */}
          <h1 className="text-3xl md:text-4xl font-bold text-[#2D2A2E] mb-4">
            {post.title}
          </h1>

          {/* Author */}
          <div className="flex items-center gap-3 mb-8 pb-8 border-b border-gray-100">
            <div className="w-10 h-10 rounded-full bg-gradient-to-br from-[#F8A5B8] to-[#E89AAB] flex items-center justify-center text-white font-bold">
              {post.author_name?.charAt(0) || 'R'}
            </div>
            <div>
              <p className="font-medium text-[#2D2A2E]">{post.author_name}</p>
              <p className="text-sm text-[#5A5A5A]">ReRoots Skincare</p>
            </div>
          </div>

          {/* Featured Products at Top (if any) */}
          {post.featured_products && post.featured_products.length > 0 && (
            <div className="mb-8">
              {post.featured_products.slice(0, 1).map(product => (
                <ShoppableProductEmbed key={product.id} product={product} />
              ))}
            </div>
          )}

          {/* Content */}
          <div 
            className="prose prose-lg max-w-none
              prose-headings:text-[#2D2A2E] prose-headings:font-bold
              prose-p:text-[#5A5A5A] prose-p:leading-relaxed
              prose-a:text-[#F8A5B8] prose-a:no-underline hover:prose-a:underline
              prose-strong:text-[#2D2A2E]
              prose-ul:text-[#5A5A5A] prose-ol:text-[#5A5A5A]
              prose-blockquote:border-l-[#F8A5B8] prose-blockquote:text-[#5A5A5A]
              prose-img:rounded-xl"
            dangerouslySetInnerHTML={{ __html: post.content }}
          />

          {/* Additional Featured Products */}
          {post.featured_products && post.featured_products.length > 1 && (
            <div className="mt-8 pt-8 border-t border-gray-100">
              <h3 className="text-xl font-bold text-[#2D2A2E] mb-4">Shop Featured Products</h3>
              {post.featured_products.slice(1).map(product => (
                <ShoppableProductEmbed key={product.id} product={product} />
              ))}
            </div>
          )}

          {/* Tags */}
          {post.tags && post.tags.length > 0 && (
            <div className="flex flex-wrap items-center gap-2 mt-8 pt-8 border-t border-gray-100">
              <Tag className="w-4 h-4 text-[#5A5A5A]" />
              {post.tags.map(tag => (
                <Badge key={tag} variant="outline" className="text-[#5A5A5A]">
                  {tag}
                </Badge>
              ))}
            </div>
          )}

          {/* References/Citations Section */}
          <ReferencesSection references={post.references} />

          {/* Share Section */}
          <div className="flex items-center justify-between mt-8 pt-8 border-t border-gray-100">
            <p className="font-medium text-[#2D2A2E]">Share this article</p>
            <div className="flex items-center gap-2">
              <Button 
                size="sm" 
                variant="outline"
                onClick={() => handleShare('twitter')}
                className="hover:bg-blue-50 hover:text-blue-500 hover:border-blue-200"
              >
                <Twitter className="w-4 h-4" />
              </Button>
              <Button 
                size="sm" 
                variant="outline"
                onClick={() => handleShare('facebook')}
                className="hover:bg-blue-50 hover:text-blue-600 hover:border-blue-200"
              >
                <Facebook className="w-4 h-4" />
              </Button>
              <Button 
                size="sm" 
                variant="outline"
                onClick={() => handleShare('copy')}
              >
                <Share2 className="w-4 h-4" />
              </Button>
            </div>
          </div>
        </div>

        {/* Related Posts */}
        {relatedPosts.length > 0 && (
          <div className="bg-[#FDF9F9] py-12 mt-12">
            <div className="max-w-6xl mx-auto px-4">
              <h2 className="text-2xl font-bold text-[#2D2A2E] mb-8 text-center">
                Related Articles
              </h2>
              <div className="grid md:grid-cols-3 gap-6">
                {relatedPosts.map(relatedPost => (
                  <Link 
                    key={relatedPost.id} 
                    to={`/blog/${relatedPost.slug}`}
                    className="group"
                  >
                    <Card className="overflow-hidden hover:shadow-lg transition-shadow">
                      <div className="aspect-video bg-gray-100">
                        {relatedPost.featured_image ? (
                          <img 
                            src={relatedPost.featured_image} 
                            alt={relatedPost.title}
                            className="w-full h-full object-cover group-hover:scale-105 transition-transform"
                          />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-[#F8A5B8]/20 to-[#F8A5B8]/5">
                            <span className="text-3xl font-bold text-[#F8A5B8]/30">R</span>
                          </div>
                        )}
                      </div>
                      <CardContent className="p-4">
                        <h3 className="font-semibold text-[#2D2A2E] line-clamp-2 group-hover:text-[#F8A5B8] transition-colors">
                          {relatedPost.title}
                        </h3>
                        <p className="text-sm text-[#5A5A5A] mt-2 line-clamp-2">
                          {relatedPost.excerpt}
                        </p>
                      </CardContent>
                    </Card>
                  </Link>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* CTA Section */}
        <div className="bg-gradient-to-r from-[#2D2A2E] to-[#3D393D] text-white py-16 px-4">
          <div className="max-w-4xl mx-auto text-center">
            <h2 className="text-2xl md:text-3xl font-bold mb-4">
              Ready to Transform Your Skin?
            </h2>
            <p className="text-white/80 mb-6">
              Discover our science-backed skincare products and start your journey to healthier skin.
            </p>
            <Link to="/products">
              <Button size="lg" className="bg-[#F8A5B8] hover:bg-[#E89AAB] text-white">
                Shop Now
                <ArrowRight className="w-4 h-4 ml-2" />
              </Button>
            </Link>
          </div>
        </div>
      </article>
    </>
  );
};

export default BlogListPage;
