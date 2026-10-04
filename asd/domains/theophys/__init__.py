"""Bausteine der Domäne Theoretische Physik (asd/domains/theophys_domain.py).

ausdruck   sicheres Einlesen von Formeln (SymPy, ohne eval fremden Codes) und rigorose Intervall-Auswertung (arb)
zeitlimit  harte Zeitlimits für Rechnungen (eigener Prozess)
lean       Lean-4-Beweise aus Vorlagen (Aussage vom Code erzeugt, Taktik fest)
spin       Quanten-Spinketten: exakte Pauli-Algebra, Hamiltonoperatoren, exakte Spektren (charakteristisches Polynom + Wurzelisolation)
ising      klassisches Ising-Modell: exakte Zustandsdichte per Transfermatrix, rigorose freie Energie
gr         Allgemeine Relativitätstheorie: Christoffel, Riemann, Ricci, Einstein, Kretschmann (symbolisch exakt)
gruppen    Gruppentheorie und Eichtheorie: SU(N)-Darstellungen, Casimir, Index, Betafunktion, Anomalien
bell       Bell-Ungleichungen: klassische Schranke (Aufzählung), Quantenwert des Singuletts (exakt)
qm         1D-Schrödinger-Spektren (numerisch, zwei Auflösungen + Richardson)
einheiten  Dimensionsanalyse (M, L, T, I, Θ)
"""
