import React, { useState, useRef } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { 
  Copy, Check, MessageSquare, Sparkles, 
  Target, ExternalLink, Star, TrendingUp,
  Users, Lightbulb, Edit3, ChevronRight,
  Camera, Clock, Award, Zap
} from "lucide-react";

// Reddit icon component
const RedditIcon = ({ className }) => (
  <svg className={className} viewBox="0 0 24 24" fill="currentColor">
    <path d="M12 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0zm5.01 4.744c.688 0 1.25.561 1.25 1.249a1.25 1.25 0 0 1-2.498.056l-2.597-.547-.8 3.747c1.824.07 3.48.632 4.674 1.488.308-.309.73-.491 1.207-.491.968 0 1.754.786 1.754 1.754 0 .716-.435 1.333-1.01 1.614a3.111 3.111 0 0 1 .042.52c0 2.694-3.13 4.87-7.004 4.87-3.874 0-7.004-2.176-7.004-4.87 0-.183.015-.366.043-.534A1.748 1.748 0 0 1 4.028 12c0-.968.786-1.754 1.754-1.754.463 0 .898.196 1.207.49 1.207-.883 2.878-1.43 4.744-1.487l.885-4.182a.342.342 0 0 1 .14-.197.35.35 0 0 1 .238-.042l2.906.617a1.214 1.214 0 0 1 1.108-.701zM9.25 12C8.561 12 8 12.562 8 13.25c0 .687.561 1.248 1.25 1.248.687 0 1.248-.561 1.248-1.249 0-.688-.561-1.249-1.249-1.249zm5.5 0c-.687 0-1.248.561-1.248 1.25 0 .687.561 1.248 1.249 1.248.688 0 1.249-.561 1.249-1.249 0-.687-.562-1.249-1.25-1.249zm-5.466 3.99a.327.327 0 0 0-.231.094.33.33 0 0 0 0 .463c.842.842 2.484.913 2.961.913.477 0 2.105-.056 2.961-.913a.361.361 0 0 0 .029-.463.33.33 0 0 0-.464 0c-.547.533-1.684.73-2.512.73-.828 0-1.979-.196-2.512-.73a.326.326 0 0 0-.232-.095z"/>
  </svg>
);

const RedditLaunchToolkit = ({ 
  referralCode,
  referralLink,
  userName = "Founding Member",
  productName = "AURA-GEN Bio-Regenerator",
  isVIP = false
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [activeTab, setActiveTab] = useState("templates");
  const [copied, setCopied] = useState(null);
  const [reviewForm, setReviewForm] = useState({
    skinType: "",
    skinConcerns: "",
    usageDuration: "",
    results: "",
    rating: 5,
    beforeAfter: false
  });
  const [generatedReview, setGeneratedReview] = useState("");

  // Target subreddits with strategies
  const targetSubreddits = [
    {
      name: "r/SkincareAddiction",
      members: "2.4M",
      strategy: "Focus on ingredients, routine help, and science-backed claims",
      bestPosts: ["Routine help", "Ingredient questions", "Before/after"],
      difficulty: "Medium",
      timing: "Best: 8-10 AM EST, Weekdays"
    },
    {
      name: "r/CanSkincare",
      members: "45K",
      strategy: "Emphasize Canadian brand, local availability, no customs",
      bestPosts: ["Product reviews", "Where to buy", "Canadian alternatives"],
      difficulty: "Easy",
      timing: "Best: 9-11 AM EST"
    },
    {
      name: "r/AsianBeauty",
      members: "1.9M",
      strategy: "PDRN is popular here - connect to K-beauty clinic treatments",
      bestPosts: ["Ingredient deep-dives", "Product comparisons", "Hauls"],
      difficulty: "Medium",
      timing: "Best: 7-9 AM EST"
    },
    {
      name: "r/30PlusSkinCare",
      members: "320K",
      strategy: "Focus on anti-aging, regeneration, mature skin concerns",
      bestPosts: ["Product reviews", "Routine updates", "What worked for me"],
      difficulty: "Easy",
      timing: "Best: 10 AM - 12 PM EST"
    },
    {
      name: "r/tretinoin",
      members: "180K",
      strategy: "PDRN pairs well with tret - healing, barrier support",
      bestPosts: ["Pairing products", "Barrier repair", "Progress posts"],
      difficulty: "Medium",
      timing: "Best: Evening EST"
    }
  ];

  // Pre-written Reddit post templates
  const postTemplates = {
    discovery: {
      title: "[Review] Finally found a Canadian PDRN serum that doesn't cost $200+",
      body: `**Skin Type:** [Your skin type]
**Climate:** Canada 🇨🇦

**TL;DR:** Found a Canadian brand called ReRoots that makes PDRN serums. Been using for [X weeks] and seeing [results].

---

So I've been on the hunt for a PDRN serum ever since I learned about it from this sub. The K-beauty ones are expensive AF with shipping and customs, and I couldn't find anything local... until now.

**The Product:** AURA-GEN Bio-Regenerator by ReRoots

**What is PDRN?** For those who don't know, it's polydeoxyribonucleotide (salmon DNA extract) - used in Korean clinics for skin regeneration and wound healing.

**My Experience:**
- [Share your actual experience]
- [Results you've noticed]
- [How it fits in your routine]

**The Deal:** They're doing a Founding Member thing right now where you can get it for way less than retail. Not trying to shill, just sharing because I know how frustrating the PDRN search is.

Happy to answer questions about the product or my experience!

---

*Edit: Since people are asking, here's the link: ${referralLink}*`,
      subreddit: "r/SkincareAddiction"
    },
    routine: {
      title: "[Routine Help] Adding PDRN to my routine - 4 week update",
      body: `**Morning:**
- Gentle cleanser
- ReRoots AURA-GEN (PDRN serum)
- Moisturizer
- SPF

**Evening:**
- Oil cleanser
- Gentle cleanser
- [Other actives if any]
- AURA-GEN
- Moisturizer

---

**Background:** [Your skin concerns]

**Why PDRN:** Wanted something for [skin regeneration/texture/healing] without the irritation of retinoids.

**Results so far:**
- Week 1: [observations]
- Week 2: [observations]  
- Week 4: [observations]

The serum itself has a nice lightweight texture, absorbs quickly, no sticky residue.

Would love to hear if anyone else has tried PDRN products! How do you layer it?`,
      subreddit: "r/SkincareAddiction"
    },
    canadian: {
      title: "PSA for Canadians: Finally a local brand doing PDRN",
      body: `Okay fellow Canadians, I know we've all struggled with:
- Insane shipping costs for K-beauty
- Customs fees that double the price
- Waiting 3-4 weeks for delivery

Just discovered ReRoots - they're a Canadian biotech skincare brand based in [city]. They make a PDRN serum called AURA-GEN.

**Why I'm excited:**
- Ships from Canada (fast + no customs!)
- Uses actual PDRN technology (not a knockoff)
- Currently doing pre-launch pricing that's actually reasonable

**Price comparison:**
- Korean brands: $80-150 USD + shipping + customs
- ReRoots: Way less (they have a founding member deal rn)

I've been using it for [X weeks] and [your experience].

Anyone else tried them? Curious to hear other Canadian experiences!

Link for anyone interested: ${referralLink}`,
      subreddit: "r/CanSkincare"
    },
    ingredient: {
      title: "[Ingredient Deep Dive] My experience with PDRN after the K-beauty hype",
      body: `So PDRN (polydeoxyribonucleotide) has been huge in K-beauty for years - it's literally what they use in Korean clinic treatments for skin regeneration.

**What is PDRN?**
- Extracted from salmon DNA
- Promotes cellular regeneration
- Used in medical settings for wound healing
- Popular in Korean "salmon injection" facials

**My search for a good PDRN serum:**
I tried a few Korean ones but the shipping and customs to Canada were brutal. Then I found a Canadian brand (ReRoots) making one called AURA-GEN.

**My experience (${reviewForm.usageDuration || "X weeks"}):**
${reviewForm.results || "[Share your results]"}

**How I use it:**
- After cleansing, before heavier products
- Both AM and PM
- Layers well under everything

**Verdict:** [Your overall thoughts]

Happy to answer questions about PDRN or this specific product!`,
      subreddit: "r/AsianBeauty"
    },
    antiaging: {
      title: "[Review] PDRN serum for 30+ skin - my honest review",
      body: `Hi everyone! I'm [age] with [skin type] skin, main concerns: [concerns].

**The product:** AURA-GEN Bio-Regenerator by ReRoots (Canadian brand)

**Why I tried it:** 
I kept reading about PDRN being the "next big thing" for mature skin - supposedly helps with cellular regeneration and has been used in Korean clinics for years.

**My results after ${reviewForm.usageDuration || "X weeks"}:**
${reviewForm.results || "[Your results]"}

**What I like:**
- [Pro 1]
- [Pro 2]
- [Pro 3]

**What could be better:**
- [Honest con if any]

**Would I repurchase?** [Yes/No and why]

**Price:** They're doing a founding member deal right now that makes it pretty affordable.

Link: ${referralLink}

Happy to answer any questions!`,
      subreddit: "r/30PlusSkinCare"
    },
    tretinoin: {
      title: "PDRN + Tretinoin combo - 6 week update on my barrier",
      body: `For those who don't know, PDRN (salmon DNA) is known for its regenerative properties and is often used post-procedure in Korean clinics.

**My hypothesis:** If it helps skin heal after lasers/needling, maybe it could help with tret irritation?

**My routine:**
- AM: Gentle cleanser → PDRN serum → Moisturizer → SPF
- PM: Gentle cleanser → Wait 20 min → Tret 0.05% → Wait 20 min → PDRN → Moisturizer

**The PDRN:** AURA-GEN by ReRoots (Canadian brand - finally found one without $50 shipping!)

**Results:**
- Less peeling than before I added PDRN
- Skin feels more "resilient"  
- Still getting the tret benefits without as much irritation

**Disclaimer:** Not a derm, just sharing my experience. YMMV.

Anyone else using PDRN with their retinoid? Curious about your experiences!`,
      subreddit: "r/tretinoin"
    }
  };

  // Comment templates for engaging with existing posts
  const commentTemplates = [
    {
      scenario: "Someone asks about PDRN",
      template: `PDRN (polydeoxyribonucleotide) is salmon DNA extract - it's been used in Korean clinics for years for skin regeneration. There's actually some solid research on it for wound healing and cellular repair.

I've been using a Canadian brand's PDRN serum for [X weeks] and noticed [your observation]. If you want to try it, ReRoots makes one called AURA-GEN that's more affordable than the K-beauty imports.`
    },
    {
      scenario: "Someone looking for Canadian skincare",
      template: `Have you looked at ReRoots? They're a Canadian biotech brand that just launched. I've been trying their PDRN serum and really liking it so far. Plus no customs or crazy shipping wait times!`
    },
    {
      scenario: "Someone with skin regeneration concerns",
      template: `You might want to look into PDRN - it's been used in Korean clinics for skin regeneration and there's research showing it helps with cellular repair. I started using a PDRN serum a few weeks ago and my [specific concern] has improved.`
    },
    {
      scenario: "Someone comparing ingredients",
      template: `PDRN is worth considering for [their concern]. It works differently than [ingredient they mentioned] - it's more about cellular regeneration at the DNA level. I've been using ReRoots' PDRN serum alongside my [other products] and it's been a good addition.`
    }
  ];

  const handleCopy = (text, id) => {
    navigator.clipboard.writeText(text);
    setCopied(id);
    toast.success("Copied to clipboard!");
    setTimeout(() => setCopied(null), 2000);
  };

  const generateReview = () => {
    const review = `**My ${reviewForm.usageDuration} Review: ReRoots AURA-GEN PDRN Serum**

**Skin Type:** ${reviewForm.skinType}
**Main Concerns:** ${reviewForm.skinConcerns}
**Rating:** ${"⭐".repeat(reviewForm.rating)}/5

---

**My Experience:**
${reviewForm.results}

${reviewForm.beforeAfter ? "**Before/After:** [Add your photos here]\n\n" : ""}**Would I recommend?** ${reviewForm.rating >= 4 ? "Yes!" : "With some caveats."}

---

*Got mine through their Founding Member program: ${referralLink}*`;
    
    setGeneratedReview(review);
    toast.success("Review generated! Edit as needed.");
  };

  const openReddit = (subreddit, title = "", body = "") => {
    const baseUrl = `https://www.reddit.com/${subreddit}/submit`;
    const params = new URLSearchParams();
    if (title) params.append("title", title);
    if (body) params.append("text", body);
    params.append("selftext", "true");
    
    window.open(`${baseUrl}?${params.toString()}`, "_blank");
  };

  return (
    <>
      {/* Trigger Button */}
      <Button 
        onClick={() => setIsOpen(true)}
        className="w-full bg-[#FF4500] hover:bg-[#FF5722] text-white font-medium"
        data-testid="reddit-toolkit-btn"
      >
        <RedditIcon className="w-5 h-5 mr-2" />
        Reddit Launch Toolkit
      </Button>

      {/* Main Dialog */}
      <Dialog open={isOpen} onOpenChange={setIsOpen}>
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-xl">
              <RedditIcon className="w-6 h-6 text-[#FF4500]" />
              Reddit Launch Toolkit
            </DialogTitle>
            <DialogDescription>
              Strategic templates and tools to build authentic presence on Reddit
            </DialogDescription>
          </DialogHeader>

          <Tabs value={activeTab} onValueChange={setActiveTab} className="mt-4">
            <TabsList className="grid grid-cols-4 w-full">
              <TabsTrigger value="templates" className="text-xs sm:text-sm">
                <Edit3 className="w-4 h-4 mr-1 hidden sm:block" />
                Templates
              </TabsTrigger>
              <TabsTrigger value="subreddits" className="text-xs sm:text-sm">
                <Target className="w-4 h-4 mr-1 hidden sm:block" />
                Subreddits
              </TabsTrigger>
              <TabsTrigger value="review" className="text-xs sm:text-sm">
                <Star className="w-4 h-4 mr-1 hidden sm:block" />
                Review Builder
              </TabsTrigger>
              <TabsTrigger value="comments" className="text-xs sm:text-sm">
                <MessageSquare className="w-4 h-4 mr-1 hidden sm:block" />
                Comments
              </TabsTrigger>
            </TabsList>

            {/* POST TEMPLATES TAB */}
            <TabsContent value="templates" className="mt-4 space-y-4">
              <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm">
                <p className="font-medium text-amber-800 flex items-center gap-2">
                  <Lightbulb className="w-4 h-4" />
                  Pro Tip: Don't just copy-paste!
                </p>
                <p className="text-amber-700 mt-1">
                  Personalize these templates with your real experience. Reddit users can spot fake reviews instantly.
                </p>
              </div>

              <div className="space-y-4">
                {Object.entries(postTemplates).map(([key, template]) => (
                  <Card key={key} className="overflow-hidden">
                    <CardHeader className="pb-2 bg-gray-50">
                      <div className="flex items-center justify-between">
                        <div>
                          <Badge variant="outline" className="text-[#FF4500] border-[#FF4500] mb-2">
                            {template.subreddit}
                          </Badge>
                          <CardTitle className="text-base">{template.title}</CardTitle>
                        </div>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => openReddit(template.subreddit.substring(2), template.title, template.body)}
                          className="shrink-0"
                        >
                          <ExternalLink className="w-4 h-4 mr-1" />
                          Post
                        </Button>
                      </div>
                    </CardHeader>
                    <CardContent className="pt-3">
                      <div className="bg-gray-50 rounded-lg p-3 max-h-48 overflow-y-auto">
                        <pre className="whitespace-pre-wrap text-xs font-mono text-gray-700">
                          {template.body}
                        </pre>
                      </div>
                      <div className="flex gap-2 mt-3">
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => handleCopy(template.body, key)}
                          className="text-xs"
                        >
                          {copied === key ? <Check className="w-3 h-3 mr-1" /> : <Copy className="w-3 h-3 mr-1" />}
                          Copy Body
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => handleCopy(template.title, `${key}-title`)}
                          className="text-xs"
                        >
                          {copied === `${key}-title` ? <Check className="w-3 h-3 mr-1" /> : <Copy className="w-3 h-3 mr-1" />}
                          Copy Title
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </TabsContent>

            {/* SUBREDDITS TAB */}
            <TabsContent value="subreddits" className="mt-4 space-y-4">
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-sm">
                <p className="font-medium text-blue-800 flex items-center gap-2">
                  <TrendingUp className="w-4 h-4" />
                  Strategy: Be Helpful First
                </p>
                <p className="text-blue-700 mt-1">
                  Spend 2-3 weeks engaging genuinely before posting about products. Answer questions, help people, build karma.
                </p>
              </div>

              <div className="grid gap-4">
                {targetSubreddits.map((sub, idx) => (
                  <Card key={idx}>
                    <CardContent className="p-4">
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-2">
                            <a 
                              href={`https://reddit.com/${sub.name}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="font-bold text-[#FF4500] hover:underline flex items-center gap-1"
                            >
                              {sub.name}
                              <ExternalLink className="w-3 h-3" />
                            </a>
                            <Badge variant="secondary" className="text-xs">
                              <Users className="w-3 h-3 mr-1" />
                              {sub.members}
                            </Badge>
                            <Badge 
                              variant="outline" 
                              className={`text-xs ${
                                sub.difficulty === "Easy" ? "border-green-500 text-green-600" :
                                sub.difficulty === "Medium" ? "border-yellow-500 text-yellow-600" :
                                "border-red-500 text-red-600"
                              }`}
                            >
                              {sub.difficulty}
                            </Badge>
                          </div>
                          
                          <p className="text-sm text-gray-600 mb-2">{sub.strategy}</p>
                          
                          <div className="flex flex-wrap gap-1 mb-2">
                            {sub.bestPosts.map((post, i) => (
                              <Badge key={i} variant="outline" className="text-xs">
                                {post}
                              </Badge>
                            ))}
                          </div>
                          
                          <p className="text-xs text-gray-500 flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {sub.timing}
                          </p>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </TabsContent>

            {/* REVIEW BUILDER TAB */}
            <TabsContent value="review" className="mt-4 space-y-4">
              <div className="bg-green-50 border border-green-200 rounded-lg p-3 text-sm">
                <p className="font-medium text-green-800 flex items-center gap-2">
                  <Award className="w-4 h-4" />
                  Authentic Reviews Win
                </p>
                <p className="text-green-700 mt-1">
                  Fill in your real experience below. Honest reviews (even with cons) are more believable and valuable.
                </p>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-4">
                  <div>
                    <Label htmlFor="skinType">Your Skin Type</Label>
                    <Input 
                      id="skinType"
                      placeholder="e.g., Combination, oily T-zone"
                      value={reviewForm.skinType}
                      onChange={(e) => setReviewForm({...reviewForm, skinType: e.target.value})}
                    />
                  </div>
                  
                  <div>
                    <Label htmlFor="skinConcerns">Main Skin Concerns</Label>
                    <Input 
                      id="skinConcerns"
                      placeholder="e.g., Fine lines, texture, dullness"
                      value={reviewForm.skinConcerns}
                      onChange={(e) => setReviewForm({...reviewForm, skinConcerns: e.target.value})}
                    />
                  </div>
                  
                  <div>
                    <Label htmlFor="usageDuration">How Long Used</Label>
                    <Input 
                      id="usageDuration"
                      placeholder="e.g., 4 weeks, 2 months"
                      value={reviewForm.usageDuration}
                      onChange={(e) => setReviewForm({...reviewForm, usageDuration: e.target.value})}
                    />
                  </div>
                  
                  <div>
                    <Label>Rating</Label>
                    <div className="flex gap-1 mt-1">
                      {[1,2,3,4,5].map((star) => (
                        <button
                          key={star}
                          onClick={() => setReviewForm({...reviewForm, rating: star})}
                          className={`p-1 ${reviewForm.rating >= star ? "text-yellow-500" : "text-gray-300"}`}
                        >
                          <Star className="w-6 h-6 fill-current" />
                        </button>
                      ))}
                    </div>
                  </div>
                  
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="beforeAfter"
                      checked={reviewForm.beforeAfter}
                      onChange={(e) => setReviewForm({...reviewForm, beforeAfter: e.target.checked})}
                      className="rounded"
                    />
                    <Label htmlFor="beforeAfter" className="text-sm cursor-pointer">
                      I have before/after photos
                    </Label>
                  </div>
                </div>
                
                <div>
                  <Label htmlFor="results">Your Results & Experience</Label>
                  <Textarea 
                    id="results"
                    placeholder="Describe what you noticed...&#10;&#10;Week 1: My skin felt more hydrated...&#10;Week 2: Started noticing smoother texture...&#10;Week 4: Fine lines around eyes look less pronounced..."
                    value={reviewForm.results}
                    onChange={(e) => setReviewForm({...reviewForm, results: e.target.value})}
                    className="h-48"
                  />
                </div>
              </div>

              <Button onClick={generateReview} className="w-full">
                <Sparkles className="w-4 h-4 mr-2" />
                Generate Reddit Review
              </Button>

              {generatedReview && (
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm flex items-center justify-between">
                      Your Generated Review
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => handleCopy(generatedReview, "review")}
                      >
                        {copied === "review" ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                      </Button>
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="bg-gray-50 rounded-lg p-3 max-h-64 overflow-y-auto">
                      <pre className="whitespace-pre-wrap text-sm font-mono text-gray-700">
                        {generatedReview}
                      </pre>
                    </div>
                    <div className="flex gap-2 mt-3">
                      <Button
                        size="sm"
                        onClick={() => openReddit("SkincareAddiction", `[Review] ${reviewForm.usageDuration} with ReRoots AURA-GEN PDRN Serum`, generatedReview)}
                        className="bg-[#FF4500] hover:bg-[#FF5722]"
                      >
                        <RedditIcon className="w-4 h-4 mr-1" />
                        Post to r/SkincareAddiction
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              )}
            </TabsContent>

            {/* COMMENTS TAB */}
            <TabsContent value="comments" className="mt-4 space-y-4">
              <div className="bg-purple-50 border border-purple-200 rounded-lg p-3 text-sm">
                <p className="font-medium text-purple-800 flex items-center gap-2">
                  <Zap className="w-4 h-4" />
                  Comments > Posts
                </p>
                <p className="text-purple-700 mt-1">
                  Helpful comments on existing threads often get more visibility than new posts. Plus, they build your credibility.
                </p>
              </div>

              <div className="space-y-4">
                {commentTemplates.map((item, idx) => (
                  <Card key={idx}>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm flex items-center gap-2">
                        <MessageSquare className="w-4 h-4 text-[#FF4500]" />
                        {item.scenario}
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="bg-gray-50 rounded-lg p-3">
                        <p className="text-sm text-gray-700">{item.template}</p>
                      </div>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => handleCopy(item.template, `comment-${idx}`)}
                        className="mt-2 text-xs"
                      >
                        {copied === `comment-${idx}` ? <Check className="w-3 h-3 mr-1" /> : <Copy className="w-3 h-3 mr-1" />}
                        Copy Template
                      </Button>
                    </CardContent>
                  </Card>
                ))}
              </div>

              {/* Quick Search Links */}
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm">Find Relevant Threads</CardTitle>
                  <CardDescription className="text-xs">
                    Search for posts where you can add value
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="flex flex-wrap gap-2">
                    {[
                      { label: "PDRN", query: "PDRN site:reddit.com" },
                      { label: "Salmon DNA skincare", query: "salmon DNA skincare site:reddit.com" },
                      { label: "Canadian skincare", query: "Canadian skincare recommendations site:reddit.com" },
                      { label: "PDRN serum review", query: "PDRN serum review site:reddit.com" },
                      { label: "Skin regeneration", query: "skin regeneration serum site:reddit.com" }
                    ].map((search, idx) => (
                      <Button
                        key={idx}
                        size="sm"
                        variant="outline"
                        onClick={() => window.open(`https://www.google.com/search?q=${encodeURIComponent(search.query)}`, "_blank")}
                        className="text-xs"
                      >
                        {search.label}
                        <ExternalLink className="w-3 h-3 ml-1" />
                      </Button>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>

          {/* Footer with tracking link */}
          <div className="mt-6 pt-4 border-t">
            <div className="flex items-center justify-between text-sm">
              <div className="text-gray-500">
                Your tracked referral link:
              </div>
              <div className="flex items-center gap-2">
                <code className="bg-gray-100 px-2 py-1 rounded text-xs">
                  {referralLink?.substring(0, 40)}...
                </code>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => handleCopy(referralLink, "link")}
                >
                  {copied === "link" ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                </Button>
              </div>
            </div>
            <p className="text-xs text-gray-400 mt-2">
              Tip: Add <code className="bg-gray-100 px-1 rounded">?utm_source=reddit&utm_medium={"{subreddit}"}</code> to track which posts convert best
            </p>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
};

export default RedditLaunchToolkit;
