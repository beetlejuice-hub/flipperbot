# Trends: what's going up, why, and where to see it early

Research for spotting items whose value jumped before Romanian sellers notice. Collected 12 November 2026.
Prices move fast; treat every number here as a dated example, not a quote.

## The idea in one line

Romanian second-hand sellers price from what they remember or from other OLX ads. When something jumps abroad
(a console before a big game, a camera on TikTok, a LEGO set after retirement), OLX prices lag by weeks.
The edge is: watch the signals that move first, then search OLX for the item at old prices.

## What makes prices jump (patterns that repeat)

1. **A big release needs the hardware.** GTA 6 (launches 19 November 2026, PS5 and Xbox Series only) emptied PS5 Pro
   stock: sold out at big retailers from end of August, eBay asks up to ~€1,400 against €899 list, ~7,000 lei in
   Romanian shops (mobilissimo, Aug 2026). Same pattern: Switch 2 launch and the Zelda 40th edition (€510 list,
   €750-900 on eBay). After launch and restocks these usually fall back: sell into the hype, don't hold.
2. **Discontinued / retired.** LEGO sets typically rise after leaving shops (Brickfact: median +97% after 5 years,
   1,882 sets; not every year's sets, 2022 lagged). ~280 sets retire end of December 2026, incl. UCS Millennium Falcon
   75192, Technic Ford GT 42154 and Koenigsegg Jesko 42173, Himeji Castle 21060. Seiko SKX (discontinued 2019) rose
   instead of falling (WatchCharts: ~+8% in a year, ~+24% in 5 years). Discontinuation is the biggest Seiko value driver.
3. **Social media nostalgia.** Old CCD digital compacts (Canon IXUS/PowerShot, Sony Cyber-shot, Kodak EasyShare,
   Nikon Coolpix, Fujifilm FinePix, ~2003-2012): KOMEHYO (Japan) says average used prices rose ~3.5x and volumes 5x;
   Gen Z wants the "film-like" look. Romanian drawers are full of them and many sell for 50-150 lei.
   Also: film cameras, iPods, cassettes (2000s albums), Y2K tech.
4. **A remake, sequel or streaming show revives an old thing.** Okami's sequel reveal pushed second-hand copies of the
   original up; Nintendo Switch Online adding Star Fox moved old Star Fox carts. Watch for game/film announcements.
5. **Supply shocks.** AI data centres ate memory: DDR5 kits roughly doubled (32 GB ~€80 → ~€167, mid-2025 → mid-2026),
   GPUs +15-19% in one month (Sept 2026), console list prices up (Sony, Nintendo Switch 2 €470 → €500 from 1 Sept
   2026). Used RAM, GPUs, SSDs, consoles and laptops ride this.
6. **List-price increases.** When a brand raises new prices (Rolex/Omega every January, Seiko in Sept 2026), good used
   examples follow over the next months, slower and smaller.
7. **Hype that collapses.** Labubu: resale down 50%+ from the 2025 peak once Pop Mart raised output to ~30M a month.
   Retro games: flat to down since the 2021 peak in real terms. Pokémon modern singles corrected 20-30% in Q1 2026
   while vintage sealed rose 15-25%. Sneaker resale: same shoes ~7% cheaper than a year ago (SneakerPulse).
   Rule: a fad spikes and falls back; a real trend keeps a higher floor after each spike.

## Where to see it: sources by category

Free and usable by the bot:
- **Our own OLX data** (best local signal, free): per model, median asking price this fortnight vs the last 2 months,
  how many new listings appear, how fast listings vanish (sold), and how many "cumpăr" (wanted) ads appear. Rising
  wanted ads + rising price + falling supply = demand ahead of sellers.
- **eBay Browse API** (we already use it): active fixed-price listings per item in Germany/EU. Sold history needs the
  Marketplace Insights API, which is limited-release (approval only).
- **Google Trends "Trending now" for Romania** (trends.google.com/trending?geo=RO): has an RSS export (~10 trends a day).
  The official Google Trends API is alpha, by application only; pytrends is archived (April 2025).
- **Wikipedia pageviews API** (free, no key, data from 2015, ~1 day lag): attention spikes for a game, console, camera
  or show; use a 30-day rolling baseline, heavy tails mean only big jumps count.

Free websites to check by hand (or read with Claude's web search):
- **Watches:** WatchCharts price indexes per brand and model (watchcharts.com/watches/price_index; API needs a paid
  Professional plan), Chrono24 price charts, monthly WatchCharts market updates. Market: index up ~9.7% in 2026 to
  August; $500-1,000 watches the strongest segment (+~17% in 12 months); Tudor +11% (Feb 2025 → Feb 2026).
- **LEGO:** BrickEconomy (values, growth, "retiring soon", monthly market recaps), Brickfact (end-of-life dates,
  value checker), Brick Fanatics retirement lists, BrickLink (sold prices).
- **Video games and consoles:** PriceCharting (loose/CIB/new prices; official API for prices, history via its
  charts), RetroCharting (GameCube/N64 medians), Stealth Optional "Weekly Watch: retro games spiking".
- **Trading cards:** Pokemon Price Tracker, PriceCharting, TCGplayer, Cardmarket (Europe's main card market),
  Card Ladder indexes. TCG market ~$15B in 2026.
- **Sneakers and streetwear:** StockX "Big Facts" reports (H1 2026: Saucony +239%, Vans resale $102 → $180,
  Supreme and Jordan back), SneakerPulse resale index, GOAT.
- **Cameras:** eBay sold, Kamerastore and MPB price lists, KOMEHYO / Japanese used market, Photorumors.
- **Vinyl:** Discogs marketplace (price history per release; monthly "most expensive sold" lists).
- **General resale news:** ResellCalendar (RAM, consoles, toys, Pokémon), The Flip Forecast newsletter, eBay
  Product Research (ex-Terapeak, free in Seller Hub, ~3 years of sold data; sell-through above ~60% is strong).
- **Romania:** compari.ro and Pricy (new-price history across Romanian shops: when new prices jump, used follows),
  eMAG stock (sold out = second-hand demand), OLX itself.

## Watch now (November 2026)

- PS5 Pro / PS5 / Xbox Series X before and right after GTA 6 (19 Nov): buy under shop price only, sell fast.
- Old CCD compacts (Canon IXUS / PowerShot SD, Sony Cyber-shot W/T series, Kodak EasyShare, Nikon Coolpix S):
  buy at 50-150 lei when they work and have a battery + charger.
- LEGO sets retiring end of December 2026, sealed (bought at a discount before or right after retirement).
- DDR5 RAM, recent GPUs (RTX 30/40, RX 6000/7000), SSDs: used prices follow the memory shortage.
- Seiko discontinued references (SKX007/009/013, SARB, Alpinist SARB017, Turtle 6309) and $500-1,000 Swiss watches
  (Tissot PRX, Hamilton Khaki, Longines HydroConquest, Oris).
- Avoid buying in on: Labubu, modern Pokémon singles, generic retro games, hyped sneakers.

## Sources

Brickfact LEGO EOL price study and end-of-life lists; BrickEconomy market recaps (March, May 2026); Brick Fanatics
retiring lists; WatchCharts price index and monthly updates (via 5dwatches, INSIGHT); watchscanning Seiko 2026 price
guide; Fratello and Time+Tide on discontinued Seikos; IBTimes, GamesRadar, Tom's Guide, mobilissimo.ro on PS5 Pro and
GTA 6; Galaxus and instant-gaming on Switch 2; Photorumors (KOMEHYO data), Gear Patrol and Mental Floss on CCD
cameras; tech-insider, verdictbits and ResellCalendar on RAM and GPUs; Campaign Asia and The Standard on Labubu;
Wackoid and Stealth Optional on retro games; Pokemon Price Tracker blog; StockX Big Facts H1 2026 (FashionUnited,
retail-news.de) and SneakerPulse; Google Search Central blog on the Trends API alpha; Wikimedia pageviews FAQ;
eBay Marketplace Insights API docs; eBay research tool guides (closo, 3dsellers); Pushsquare and comicbook.com on
remakes and sequels. Collected November 2026.
