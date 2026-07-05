import { Link } from "react-router-dom";

function FilmIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 6.5h16v11H4zM8 6.5v11M16 6.5v11M4 10h4m8 0h4M4 14h4m8 0h4M7 3.5l2 3m3-3 2 3m3-3 2 3" />
    </svg>
  );
}

function NotFound({ navigation }) {
  return (
    <main className="app-shell not-found-shell">
      <div className="ambient ambient-one" />
      <div className="ambient ambient-two" />

      <section className="recommendation-panel not-found-panel">
        {navigation}

        <div className="not-found-card" role="status">
          <div className="not-found-icon">
            <FilmIcon />
          </div>
          <p className="section-kicker">404 · Missing reel</p>
          <h1>This scene is not in the cut.</h1>
          <p>
            The page you opened does not exist, or the link may have changed.
            Let’s get you back to the movies.
          </p>
          <Link className="collection-home-button" to="/">
            Back to Home
          </Link>
        </div>
      </section>

      <footer>
        <FilmIcon />
        <span>Thoughtful picks, one movie at a time.</span>
      </footer>
    </main>
  );
}

export default NotFound;
