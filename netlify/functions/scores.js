exports.handler = async (event) => {
  const API_TOKEN = '49b916e7852b422187139132b9cb6ad7';
  const url = 'https://api.football-data.org/v4/competitions/WC/matches';

  try {
    const response = await fetch(url, {
      headers: { 'X-Auth-Token': API_TOKEN }
    });
    const data = await response.json();

    return {
      statusCode: 200,
      headers: {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Cache-Control': 'public, max-age=55'
      },
      body: JSON.stringify(data)
    };
  } catch (error) {
    return {
      statusCode: 500,
      body: JSON.stringify({ error: 'Failed to fetch scores' })
    };
  }
};
