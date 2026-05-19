package com.digitalbank.predictbackend.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationConverter;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.CorsConfigurationSource;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;

import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.security.web.authentication.www.BasicAuthenticationFilter;
import org.springframework.web.filter.OncePerRequestFilter;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.util.List;
import java.util.Map;

/**
 * Configuration de sécurité Spring Security — OAuth2 Resource Server.
 *
 * Ce backend valide les tokens JWT émis par Keycloak (realm: digitalbank-realm).
 * La validation repose sur la clé publique JWKS récupérée automatiquement via :
 *   http://localhost:8081/realms/digitalbank-realm/.well-known/openid-configuration
 *
 * Architecture : API Stateless → pas de session HTTP, pas de CSRF.
 */
@Configuration
@EnableWebSecurity
@EnableMethodSecurity // Active @PreAuthorize / @PostAuthorize sur les méthodes
public class SecurityConfig {

    // ──────────────────────────────────────────────────────────────────────────
    // Filtre de sécurité principal
    // ──────────────────────────────────────────────────────────────────────────

    @Bean
    public SecurityFilterChain securityFilterChain(HttpSecurity http) throws Exception {
        http
            // 1. Désactiver CSRF — API REST stateless, tokens JWT, pas de sessions
            .csrf(csrf -> csrf.disable())

            // 2. CORS — autorise le frontend React sur http://localhost:5173 / 3000
            .cors(cors -> cors.configurationSource(corsConfigurationSource()))

            // 3. Politique de session : STATELESS (aucune session HTTP créée)
            .sessionManagement(session ->
                session.sessionCreationPolicy(SessionCreationPolicy.STATELESS)
            )

            // 4. Règles d'autorisation par route
            .authorizeHttpRequests(auth -> auth
                // Expose les préflights CORS sans authentification
                .requestMatchers(HttpMethod.OPTIONS, "/**").permitAll()
                .requestMatchers(HttpMethod.POST, "/api/v1/predictions").hasRole("AGENT_IA")
                .requestMatchers(HttpMethod.PUT, "/api/v1/predictions/**").hasRole("AGENT_IA")
                .requestMatchers(HttpMethod.GET, "/api/v1/predictions/**").hasAnyRole("CONSEILLER", "PORTEFEUILLEUR", "DIRECTEUR")
                .requestMatchers("/api/v1/admin/**").hasRole("DIRECTEUR")
                .requestMatchers("/api/v1/actions/**").hasAnyRole("CONSEILLER", "PORTEFEUILLEUR", "DIRECTEUR")
                .requestMatchers("/api/v1/reclamations/**").hasAnyRole("CONSEILLER", "PORTEFEUILLEUR", "DIRECTEUR")
                .requestMatchers("/api/v1/banquiers/me/**").authenticated()
                .requestMatchers("/api/v1/banquiers/**").hasRole("DIRECTEUR")
                .requestMatchers("/api/v1/debug/**").permitAll()
                .anyRequest().authenticated()
            )

            // 5. Configurer le Resource Server JWT avec notre convertisseur de rôles Keycloak
            .oauth2ResourceServer(oauth2 ->
                oauth2.jwt(jwt ->
                    jwt.jwtAuthenticationConverter(jwtAuthenticationConverter())
                )
            )

            // 6. Ajouter le filtre de debug après l'authentification
            .addFilterAfter(new OncePerRequestFilter() {
                @Override
                protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain filterChain)
                        throws ServletException, IOException {
                    org.springframework.security.core.Authentication auth = org.springframework.security.core.context.SecurityContextHolder.getContext().getAuthentication();
                    if (auth instanceof JwtAuthenticationToken jwtAuth) {
                        System.out.println("🔍 [DEBUG SECURITY] Path: " + request.getRequestURI());
                        System.out.println("   - Principal: " + jwtAuth.getName());
                        System.out.println("   - Authorities (Roles): " + jwtAuth.getAuthorities());
                        System.out.println("   - Claims (Agence ID): " + jwtAuth.getToken().getClaim("agence_id"));
                        System.out.println("   - Claims (Issuer): " + jwtAuth.getToken().getIssuer());
                    } else {
                        System.out.println("⚠️ [DEBUG SECURITY] Aucune authentification JWT trouvée pour : " + request.getRequestURI());
                    }
                    filterChain.doFilter(request, response);
                }
            }, BasicAuthenticationFilter.class);

        return http.build();
    }

    // ──────────────────────────────────────────────────────────────────────────
    // Convertisseur JWT → Authentication (avec rôles Keycloak)
    // ──────────────────────────────────────────────────────────────────────────

    /**
     * Bean PasswordEncoder — requis par AuthController pour les opérations
     * de hash en interne (ex: comparaison de mots de passe legacy).
     * L'authentification principale est désormais déléguée à Keycloak.
     */
    @Bean
    public PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder();
    }

    @Bean
    public JwtAuthenticationConverter jwtAuthenticationConverter() {
        JwtAuthenticationConverter converter = new JwtAuthenticationConverter();
        // Délègue l'extraction des rôles à notre convertisseur Keycloak
        converter.setJwtGrantedAuthoritiesConverter(new JwtRoleConverter());
        return converter;
    }

    // ──────────────────────────────────────────────────────────────────────────
    // Configuration CORS
    // ──────────────────────────────────────────────────────────────────────────

    /**
     * Autorise le frontend React (http://localhost:5173 / 3000) à appeler ce backend.
     * Le header "Authorization" est explicitement exposé pour transmettre les JWT.
     */
    @Bean
    public CorsConfigurationSource corsConfigurationSource() {
        CorsConfiguration configuration = new CorsConfiguration();

        // Origines autorisées
        configuration.setAllowedOrigins(List.of("http://localhost:5173", "http://localhost:3000"));

        // Méthodes HTTP autorisées
        configuration.setAllowedMethods(List.of(
            "GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"
        ));

        // Headers autorisés
        configuration.setAllowedHeaders(List.of(
            "Authorization", "Content-Type", "Accept", "Origin", "X-Requested-With"
        ));

        // Headers exposés
        configuration.setExposedHeaders(List.of("Authorization"));

        configuration.setAllowCredentials(true);
        configuration.setMaxAge(3600L);

        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/**", configuration);
        return source;
    }
}
