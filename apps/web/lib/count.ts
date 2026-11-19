/** The counting script, served from our own public/ (GoatCounter 2.7.0's count.js, unchanged). It sends to
 *  stats.datasteg.com/count, the only public GoatCounter path (admin/deploy/compose.yml). no_onload and no_events:
 *  components/Counter.tsx counts each page, including pages reached by client-side navigation, which the script
 *  alone misses, and the PDF and CSV downloads. Kept out of the client module so the server layout can read it. */
export const COUNT_SCRIPT = {
  src: '/count.js',
  endpoint: 'https://stats.datasteg.com/count',
  settings: JSON.stringify({ no_onload: true, no_events: true }),
};
