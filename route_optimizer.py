"""
Route Optimization Module for medAIssit
Handles all route optimization algorithms including TSP solving and heuristics
"""

import itertools
from math import radians, sin, cos, sqrt, atan2


def haversine(lat1, lon1, lat2, lon2):
    """Calculate distance between two coordinates using Haversine formula"""
    R = 6371  # Earth radius in km
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c  # Distance in km


def calculate_total_route_distance(route, start_location):
    """Calculate total round-trip distance for a given route"""
    if not route:
        return 0
    
    total_distance = 0
    current_location = start_location
    
    # Visit all patients in order
    for patient in route:
        distance = haversine(current_location[0], current_location[1], 
                           patient.latitude, patient.longitude)
        total_distance += distance
        current_location = (patient.latitude, patient.longitude)
    
    # Return to starting point
    return_distance = haversine(current_location[0], current_location[1], 
                               start_location[0], start_location[1])
    total_distance += return_distance
    
    return total_distance


def nearest_neighbor_with_return(patients, start_location):
    """Improved nearest neighbor that considers return distance"""
    if not patients:
        return []
    
    optimized_route = []
    remaining_patients = patients[:]
    current_location = start_location
    
    while remaining_patients:
        best_patient = None
        best_total_distance = float('inf')
        
        for patient in remaining_patients:
            # Calculate distance to this patient
            distance_to_patient = haversine(current_location[0], current_location[1], 
                                          patient.latitude, patient.longitude)
            
            # Calculate distance from this patient back to start
            distance_to_start = haversine(patient.latitude, patient.longitude, 
                                        start_location[0], start_location[1])
            
            # Estimate total remaining distance if we choose this patient
            # This is a heuristic: current distance + return distance + rough estimate of remaining
            remaining_others = [p for p in remaining_patients if p != patient]
            estimated_remaining = len(remaining_others) * 5 if remaining_others else 0  # Rough estimate
            
            total_estimated_distance = distance_to_patient + distance_to_start + estimated_remaining
            
            if total_estimated_distance < best_total_distance:
                best_total_distance = total_estimated_distance
                best_patient = patient
        
        if best_patient:
            optimized_route.append(best_patient)
            remaining_patients.remove(best_patient)
            current_location = (best_patient.latitude, best_patient.longitude)
    
    return optimized_route


def tsp_solver_small(patients, start_location, max_patients=8):
    """Solve TSP exactly for small number of patients (≤8)"""
    if len(patients) > max_patients:
        return None  # Too many patients for exact solution
    
    if not patients:
        return []
    
    best_route = None
    best_distance = float('inf')
    
    # Try all possible permutations
    for route_permutation in itertools.permutations(patients):
        total_distance = calculate_total_route_distance(route_permutation, start_location)
        
        if total_distance < best_distance:
            best_distance = total_distance
            best_route = list(route_permutation)
    
    return best_route


def tsp_2opt_improvement(route, start_location, max_iterations=100):
    """Improve route using 2-opt local search"""
    if len(route) < 4:
        return route  # 2-opt needs at least 4 nodes
    
    current_route = route[:]
    current_distance = calculate_total_route_distance(current_route, start_location)
    
    improved = True
    iteration = 0
    
    while improved and iteration < max_iterations:
        improved = False
        iteration += 1
        
        for i in range(len(current_route) - 1):
            for j in range(i + 2, len(current_route)):
                # Create new route by reversing the segment between i and j
                new_route = current_route[:]
                new_route[i:j+1] = reversed(new_route[i:j+1])
                
                new_distance = calculate_total_route_distance(new_route, start_location)
                
                if new_distance < current_distance:
                    current_route = new_route
                    current_distance = new_distance
                    improved = True
                    break
            
            if improved:
                break
    
    return current_route


def optimize_patient_route(patients, start_location, desired_day=None, only_unseen=True):
    """
    Main optimization function - chooses the best algorithm based on problem size
    
    Args:
        patients: List of patient objects with latitude/longitude
        start_location: Tuple of (lat, lon) for starting point
        desired_day: Optional string for logging purposes
        only_unseen: If True, only optimize routes for patients not yet seen
    
    Returns:
        List of patients in optimized order
    """
    if not patients:
        return []

    # Filter patients with GPS coordinates and optionally only unseen patients
    if only_unseen:
        patients_with_gps = [p for p in patients 
                           if p.latitude is not None and p.longitude is not None and not p.seen]
        filter_msg = "unseen patients with GPS"
    else:
        patients_with_gps = [p for p in patients 
                           if p.latitude is not None and p.longitude is not None]
        filter_msg = "patients with GPS"
    
    if not patients_with_gps:
        if desired_day:
            print(f"ℹ️  No {filter_msg} found for {desired_day}")
        return []

    if desired_day:
        print(f"🚗 Optimizing route for {len(patients_with_gps)} {filter_msg} on {desired_day}")
    else:
        print(f"🚗 Optimizing route for {len(patients_with_gps)} {filter_msg}")
    
    # Choose optimization method based on number of patients
    if len(patients_with_gps) <= 8:
        print("🎯 Using exact TSP solver (≤8 patients)")
        optimized_route = tsp_solver_small(patients_with_gps, start_location)
    else:
        print("🧭 Using improved nearest neighbor heuristic (>8 patients)")
        optimized_route = nearest_neighbor_with_return(patients_with_gps, start_location)
        
        # Apply 2-opt improvement
        print("🔧 Applying 2-opt improvements...")
        optimized_route = tsp_2opt_improvement(optimized_route, start_location)

    # Calculate and display route statistics
    total_distance = calculate_total_route_distance(optimized_route, start_location)
    print(f"📊 Total round-trip distance: {total_distance:.2f} km")
    print(f"✅ Route optimization completed!")
    
    return optimized_route


def compare_route_algorithms(patients, start_location):
    """Compare different routing algorithms (for testing/debugging)"""
    if not patients or len(patients) > 10:  # Limit for performance
        print("⚠️ Too many patients for algorithm comparison or no patients provided")
        return
    
    print("\n📈 ROUTE COMPARISON:")
    
    # Original nearest neighbor (simple version)
    original_route = []
    remaining = patients[:]
    current_pos = start_location
    while remaining:
        next_patient = min(remaining, key=lambda p: haversine(
            current_pos[0], current_pos[1], p.latitude, p.longitude
        ))
        original_route.append(next_patient)
        remaining.remove(next_patient)
        current_pos = (next_patient.latitude, next_patient.longitude)
    
    original_distance = calculate_total_route_distance(original_route, start_location)
    
    # Improved nearest neighbor with return consideration
    improved_route = nearest_neighbor_with_return(patients, start_location)
    improved_distance = calculate_total_route_distance(improved_route, start_location)
    
    # Exact TSP (if feasible)
    exact_route = None
    exact_distance = None
    if len(patients) <= 8:
        exact_route = tsp_solver_small(patients, start_location)
        if exact_route:
            exact_distance = calculate_total_route_distance(exact_route, start_location)
    
    # Display results
    print(f"Original Nearest Neighbor: {original_distance:.2f} km")
    print(f"Improved Nearest Neighbor: {improved_distance:.2f} km ({((improved_distance - original_distance) / original_distance * 100):+.1f}%)")
    
    if exact_distance:
        print(f"Exact TSP Solution: {exact_distance:.2f} km ({((exact_distance - original_distance) / original_distance * 100):+.1f}%)")
        print(f"Improvement vs Original: {((original_distance - exact_distance) / original_distance * 100):.1f}%")
    
    print("=" * 50)


def get_algorithm_info(patient_count):
    """Return information about which algorithm will be used"""
    if patient_count <= 8:
        return {
            "algorithm": "Exact TSP",
            "description": "Optimal solution using exhaustive search",
            "complexity": "O(n!)",
            "guaranteed_optimal": True
        }
    else:
        return {
            "algorithm": "Improved Heuristic + 2-opt",
            "description": "Smart nearest neighbor with local optimization",
            "complexity": "O(n²)",
            "guaranteed_optimal": False
        }
