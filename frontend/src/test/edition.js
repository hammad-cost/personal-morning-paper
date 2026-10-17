// Shared test fixture: a small edition shaped like GET /api/edition/today.

export const sampleEdition = {
  id: 'ed-2026-10-17-1',
  edition_number: 1,
  date: '2026-10-17',
  reading_minutes: 4,
  writer: 'ai',
  three_takeaways: [
    { text: 'Rogue AI agents breached live systems.', article_id: 'a1' },
    { text: 'Vulnerability backlogs more than doubled.', article_id: 'a2' },
    { text: 'NASA named a new Marshall director.', article_id: 'a3' },
  ],
  connect_the_dots: { text: 'Both stories are about trust in automation.', article_ids: ['a1', 'a2'] },
  mind_vitamin: { title: 'Read slowly', content: 'One idea, understood well.' },
  recall_quiz: [],
  sections: ['AI Agents', 'Cybersecurity', 'World News'],
  articles: [
    { id: 'a1', topic: 'AI Agents', headline: 'Rogue AI agents broke into live systems', summary: 'Officials said agents acted without permission.', why_it_matters: 'You follow AI agents.', source_name: 'Reuters', url: 'https://news.test/1', is_lead: true, is_explore: false, label: null, skipped: false, clicked: false },
    { id: 'a2', topic: 'Cybersecurity', headline: 'Vulnerability backlogs grew 131%', summary: 'A report found fixes lag behind.', why_it_matters: 'Security is core for you.', source_name: 'CyberScoop', url: 'https://news.test/2', is_lead: false, is_explore: false, label: null, skipped: false, clicked: false },
    { id: 'a3', topic: 'World News', headline: 'Sanctions row deepens', summary: 'Leaders traded statements.', why_it_matters: 'Something outside your usual reading.', source_name: 'BBC News', url: 'https://news.test/3', is_lead: false, is_explore: true, label: 'Something new', skipped: false, clicked: false },
  ],
}
