# Project Overview

## Problem

Infrastructure and real-asset decisions in Latin America often rely on fragmented environmental, territorial, and financial information. This makes it difficult to distinguish observed evidence from assumptions and to prioritize additional studies.

## Solution

Los Causas Espaciales converts verifiable Earth observations into time series, statistically tested trends, and preliminary investment intelligence. The MVP analyzes real locations with NASA POWER and clearly separates `REAL_DATA`, `CACHED_DATA`, `MODEL_ESTIMATE`, `USER_ASSUMPTION`, `ILLUSTRATIVE_DEMO`, and `DATA_UNAVAILABLE`.

## Users and value proposition

Investment funds, asset managers, project developers, engineers, environmental specialists, researchers, and public institutions receive scientific traceability through a common workflow for climate, energy, hazards, environment, territorial restrictions, infrastructure, and investment.

## Innovation and potential impact

The innovation is the connection between four scientific questions — what is changing, where, by how much, and with what statistical evidence — and a fifth decision question: what could those changes mean for real assets? The platform does not confuse correlation, causality, and prediction.

## Architecture

Next.js, MapLibre, and Recharts consume a FastAPI service. Source connectors feed normalized contracts; statistical, geospatial, and financial engines remain separate. A local cache preserves public responses and avoids redundant calls.
